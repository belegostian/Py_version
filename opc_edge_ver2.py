import asyncio
import copy
import logging
import statistics

from asyncua import Client, ua
from asyncua import Server
from asyncua.common.methods import uamethod
from asyncua.common.xmlexporter import XmlExporter


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


class MyClient:
    def __init__(self, url, handler):
        self.client = Client(url)
        self.handler = handler

    async def start(self):
        _logger.info("Root node is: %r", self.client.nodes.root)
        _logger.info(
            "Children of root are: %r", await self.client.nodes.root.get_children()
        )

        data = self.client.get_node(ua.NodeId(7, 2))
        threshold_high = self.client.get_node(ua.NodeId(9, 2))
        threshold_low = self.client.get_node(ua.NodeId(10, 2))

        sub = await self.client.create_subscription(50, self.handler)
        handle = await sub.subscribe_data_change(data)

        data = copy.copy(await data.read_value())
        threshold_high = copy.copy(await threshold_high.read_value())
        threshold_low = copy.copy(await threshold_low.read_value())

        return data, threshold_high, threshold_low

    async def stop(self):
        await self.client.disconnect()  # or whatever method you use to close the connection

    async def run(self):
        while True:
            if self.handler.has_data_changed():
                changed_data = self.handler.get_changed_data()
                ...
            await asyncio.sleep(0.5)


class Server:
    def __init__(self, data, threshold_high, threshold_low):
        self.server = ...  # initialize your server
        self.data = data
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low

    async def start(self):
        temp_sm_1 = await sensor_monitor_type.add_object(
            idx, "temp_sm_1", sensor_monitor_type
        )
        tsm_data1 = await temp_sm_1.add_variable(idx, "tsm_data1", self.data)
        tsm_config1 = await temp_sm_1.add_variable(
            idx, "tsm_config1", [self.threshold_high, self.threshold_low]
        )

    async def stop(self):
        ...  # implement your server stop/cleanup logic

    async def run(self):
        while True:
            ...
            await asyncio.sleep(0.5)


async def main():
    handler = SubHandler()

    my_client = MyClient(
        url="opc.tcp://localhost:4850/freeopcua/temp_sensor1/", handler=handler
    )
    data, threshold_high, threshold_low = await my_client.start()

    server = Server(data, threshold_high, threshold_low)
    await server.start()

    await asyncio.gather(client.run(), server.run())


if __name__ == "__main__":
    asyncio.run(main())
