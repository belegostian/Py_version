import asyncio
import copy
import logging
from asyncua import Client, ua

_LOGGER = logging.getLogger(__name__)
_SERVER_URL = "opc.tcp://localhost:4860/freeopcua/edge/"
_NAMESPACE_URI = "http://sample.sensor2hmi.io"


class SubHandler(object):
    def __init__(self):
        self.data_changed = False
        self.changed_data = None

    def datachange_notification(self, node, val, data):
        self.data_changed = True
        self.changed_data = val

    def get_changed_data(self):
        self.data_changed = False  # reset flag
        return self.changed_data

    def has_data_changed(self):
        return self.data_changed

    def event_notification(self, event):
        pass


class AsyncUAClient:
    def __init__(self, url):
        self.url = url
        self.client = Client(url=self.url)

    async def get_data(self, node_id):
        data_node = self.client.get_node(ua.NodeId(node_id, 2))
        return copy.copy(await data_node.read_value())

    async def call_method(self, node_path, method_name, data):
        node = await self.client.nodes.root.get_child(node_path)
        return await node.call_method(method_name, data)

    async def create_subscription(self, handler):
        return await self.client.create_subscription(500, handler)

    async def subscribe_to_data_change(self, sub, node_path):
        data_node = await self.client.nodes.root.get_child(node_path)
        return await sub.subscribe_data_change(data_node)

    async def subscribe_to_events(self, sub):
        return await sub.subscribe_events()


async def main():
    client = AsyncUAClient(_SERVER_URL)
    async with client.client as ua_client:
        _LOGGER.info("Root node is: %r", ua_client.nodes.root)
        _LOGGER.info(
            "Children of root are: %r", await ua_client.nodes.root.get_children()
        )

        idx = await ua_client.get_namespace_index(_NAMESPACE_URI)
        _LOGGER.info("index of our namespace is %s", idx)

        # get data
        data = await client.get_data(7)

        # call ua method
        mu, sigma = await client.call_method(
            ["0:Objects", "2:temp_sm_1"], "2:tsm_analyze1", data
        )

        # subscribing to a variable node & event
        handler = SubHandler()
        sub = await client.create_subscription(handler)
        handle_data = await client.subscribe_to_data_change(
            sub, ["0:Objects", "2:temp_sm_1", "2:tsm_data1"]
        )
        handle_alarm = await client.subscribe_to_events(sub)

        while True:
            if handler.has_data_changed():
                changed_data = handler.get_changed_data()
                mu, sigma = await client.call_method(
                    ["0:Objects", "2:temp_sm_1"], "2:tsm_analyze1", changed_data
                )
                print(
                    f"the mean value & standard deviation of the data is {mu} & {sigma}"
                )
            await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
