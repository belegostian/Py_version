import asyncio
import copy
import logging
import random

from asyncua import ua, Server
from asyncua.common.xmlexporter import XmlExporter

# Configure logger
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

# Define constants
SERVER_ENDPOINT = "opc.tcp://localhost:4850/freeopcua/temp_sensor1/"
SERVER_NAME = "Temperature_Sensor1"
SECURITY_POLICIES = [
    ua.SecurityPolicyType.NoSecurity,
    ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
    ua.SecurityPolicyType.Basic256Sha256_Sign,
]
URI = "http://sample.sensor2hmi.io"


class SubHandler(object):
    """Subscription Handler to receive events from server for a subscription"""

    def datachange_notification(self, node, val, data):
        _logger.warning("Python: New data change event %s %s", node, val)

    def event_notification(self, event):
        _logger.warning("Python: New event %s", event)


class TempSensorServer(object):
    """Temperature sensor server implementation"""

    @staticmethod
    def generate_temperature(mu=25, sigma=1, n=100):
        return [random.normalvariate(mu, sigma) for _ in range(n)]

    @staticmethod
    async def setup_server():
        server = Server()
        await server.init()
        server.set_endpoint(SERVER_ENDPOINT)
        server.set_server_name(SERVER_NAME)
        server.set_security_policy(SECURITY_POLICIES)
        return server

    @staticmethod
    async def create_namespace(server):
        idx = await server.register_namespace(URI)
        _logger.info(f"Namespace index: {idx}")
        return idx

    @staticmethod
    async def create_sensor_type(server, idx):
        sensor_type = await server.nodes.base_object_type.add_object_type(
            idx, "temp_sensor"
        )
        await (
            await sensor_type.add_property(idx, "device_id", "A01")
        ).set_modelling_rule(True)
        await (
            await sensor_type.add_variable(
                idx, "data", ua.Variant([], ua.VariantType.Double)
            )
        ).set_modelling_rule(True)
        await (
            await sensor_type.add_property(idx, "status", "idle")
        ).set_modelling_rule(True)
        return sensor_type

    @staticmethod
    async def instantiate_sensor_node(sensor_type, idx):
        temp_sensor_1 = await sensor_type.add_object(idx, "temp_sensor_1", sensor_type)
        threshold_high_1 = await temp_sensor_1.add_property(idx, "threshold_high", 28.0)
        threshold_low_1 = await temp_sensor_1.add_property(idx, "threshold_low", 22.0)
        data_1 = await temp_sensor_1.get_child(["2:data"])
        status_1 = await temp_sensor_1.get_child(["2:status"])
        await status_1.set_writable()
        return temp_sensor_1, data_1, status_1, threshold_high_1, threshold_low_1

    @staticmethod
    async def export_nodes_to_xml(server, nodes):
        exporter = XmlExporter(server)
        await exporter.build_etree(nodes)
        await exporter.write_xml("Temperature_Sensor1.xml")

    @staticmethod
    async def create_event(server):
        status_change_event = await server.get_event_generator()
        status_change_event.Severity = 300
        return status_change_event

    @staticmethod
    async def update_status(status_node, status_change_event, new_status):
        await status_node.write_value(new_status)
        await status_change_event.trigger(message=f"status changed: {new_status}")

    @staticmethod
    async def update_temperature_data(data_node):
        temp_data = await data_node.read_value()
        temp_data = copy.copy(temp_data)
        temp_data = TempSensorServer.generate_temperature()
        await data_node.write_value(temp_data)

    @staticmethod
    async def main():
        server = await TempSensorServer.setup_server()
        idx = await TempSensorServer.create_namespace(server)
        sensor_type = await TempSensorServer.create_sensor_type(server, idx)
        nodes = await TempSensorServer.instantiate_sensor_node(sensor_type, idx)
        await TempSensorServer.export_nodes_to_xml(server, nodes)
        status_change_event = await TempSensorServer.create_event(server)

        # create subscription
        handler = SubHandler()
        sub = await server.create_subscription(50, handler)
        await sub.subscribe_events()

        async with server:
            while True:
                # update status and temperature data
                await TempSensorServer.update_status(
                    nodes[2], status_change_event, "running"
                )
                await TempSensorServer.update_temperature_data(nodes[1])
                await TempSensorServer.update_status(
                    nodes[2], status_change_event, "idle"
                )
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(TempSensorServer.main())
