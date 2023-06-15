import asyncio
import copy
import logging

from asyncua import Client, ua


_logger = logging.getLogger(__name__)


class SubHandler(object):
    def __init__(self):
        self.data_changed = False
        self.changed_data = None

    def datachange_notification(self, node, val, data):
        self.data_changed = True
        self.changed_data = val
        # _logger.warn("Python: New data change event %s %s", node, val)

    def get_changed_data(self):
        self.data_changed = False  # reset flag
        return self.changed_data

    def has_data_changed(self):
        return self.data_changed

    def event_notification(self, event):
        pass
        # _logger.warn("Python: New event %s", event)


async def main():
    url = "opc.tcp://localhost:4860/freeopcua/edge/"
    async with Client(url=url) as client:
        _logger.info("Root node is: %r", client.nodes.root)
        _logger.info("Children of root are: %r", await client.nodes.root.get_children())

        uri = "http://sample.sensor2hmi.io"
        idx = await client.get_namespace_index(uri)
        _logger.info("index of our namespace is %s", idx)

        # get data
        data_node = client.get_node(ua.NodeId(7, 2))
        data = copy.copy(await data_node.read_value())

        # call ua method
        # tsm1 = client.get_node(ua.NodeId(4, 2))
        tsm1 = await client.nodes.root.get_child(["0:Objects", "2:temp_sm_1"])
        mu, sigma = await tsm1.call_method("2:tsm_analyze1", data)

        # subscribing to a variable node & event
        data_node = await client.nodes.root.get_child(
            ["0:Objects", "2:temp_sm_1", "2:tsm_data1"]
        )
        handler = SubHandler()
        sub = await client.create_subscription(500, handler)
        handle_data = await sub.subscribe_data_change(data_node)
        handle_alarm = await sub.subscribe_events()

        while True:
            if handler.has_data_changed():
                changed_data = handler.get_changed_data()
                mu, sigma = await tsm1.call_method("2:tsm_analyze1", changed_data)
                print(
                    f"the mean value & standard deviation of the data is {mu} & {sigma}"
                )
            await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
