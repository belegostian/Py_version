import asyncio
import copy
import logging
import statistics

from asyncua import Client, Server, ua
from asyncua.common.methods import uamethod
from asyncua.common.xmlexporter import XmlExporter

_logger = logging.getLogger(__name__)

# Server settings
SERVER_ENDPOINT = "opc.tcp://localhost:4860/freeopcua/edge/"
SERVER_NAME = "Edge_Server1"
SECURITY_POLICIES = [
    ua.SecurityPolicyType.NoSecurity,
    ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
    ua.SecurityPolicyType.Basic256Sha256_Sign,
]
NAMESPACE_URI = "http://sample.sensor2hmi.io"

# Client settings
CLIENT_URL = "opc.tcp://localhost:4850/freeopcua/temp_sensor1/"


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


@uamethod
def temp_data_preprocess(parent, data):
    mean = statistics.mean(data)
    std_deviation = statistics.stdev(data)
    return mean, std_deviation


class EdgeServer:
    @staticmethod
    async def init_server():
        server = Server()
        await server.init()
        server.set_endpoint(SERVER_ENDPOINT)
        server.set_server_name(SERVER_NAME)
        server.set_security_policy(SECURITY_POLICIES)
        idx = await server.register_namespace(NAMESPACE_URI)
        _logger.info(f"Server Namespace index: {idx}")
        return server, idx

    @staticmethod
    async def create_sensor_monitor_type(server, idx):
        sensor_monitor_type = await server.nodes.base_object_type.add_object_type(
            idx, "sensor_monitor"
        )
        await (
            await sensor_monitor_type.add_variable(idx, "sensor_status", "idle")
        ).set_modelling_rule(True)
        await (
            await sensor_monitor_type.add_variable(
                idx, "data", ua.Variant([], ua.VariantType.Float)
            )
        ).set_modelling_rule(True)
        return sensor_monitor_type


class SensorClient:
    @staticmethod
    async def init_client():
        client = Client(url=CLIENT_URL)
        await client.connect()
        idx = await client.get_namespace_index(NAMESPACE_URI)
        _logger.info(f"Client Namespace index: {idx}")

        temp_sensor = client.get_node(ua.NodeId(5, 2))
        data = client.get_node(ua.NodeId(7, 2))
        state = client.get_node(ua.NodeId(8, 2))
        threshold_high = client.get_node(ua.NodeId(9, 2))
        threshold_low = client.get_node(ua.NodeId(10, 2))

        data_value = copy.copy(await data.read_value())
        state_value = copy.copy(await state.read_value())
        threshold_high_value = copy.copy(await threshold_high.read_value())
        threshold_low_value = copy.copy(await threshold_low.read_value())

        return (
            client,
            idx,
            temp_sensor,
            data,
            state,
            threshold_high,
            threshold_low,
            data_value,
            state_value,
            threshold_high_value,
            threshold_low_value,
        )

    @staticmethod
    async def subscribe_to_data_change(client, data):
        handler = SubHandler()
        sub = await client.create_subscription(50, handler)
        handle = await sub.subscribe_data_change(data)
        return sub, handler


class TempMonitor:
    @staticmethod
    async def instantiate_temp_monitor(
        idx, server, sensor_monitor_type, data, state, threshold_high, threshold_low
    ):
        temp_sm_1 = await server.nodes.objects.add_object(
            idx, "temp_sm_1", sensor_monitor_type
        )
        tsm_data1 = await temp_sm_1.add_variable(idx, "tsm_data1", data)
        tsm_state1 = await temp_sm_1.add_variable(idx, "tsm_state1", state)
        await tsm_state1.set_writable()
        tsm_config1 = await temp_sm_1.add_variable(
            idx, "tsm_config1", [threshold_high, threshold_low]
        )
        await tsm_config1.set_writable()
        tsm_analyze1 = await temp_sm_1.add_method(
            idx,
            "tsm_analyze1",
            temp_data_preprocess,
            [ua.VariantType.Float],
            [ua.VariantType.Float, ua.VariantType.Float],
        )
        await tsm_config1.set_writable()
        tsm_op_mode1 = await temp_sm_1.add_property(idx, "tsm_op_mode1", "normal")
        return temp_sm_1, tsm_data1, tsm_state1, tsm_config1, tsm_op_mode1, tsm_analyze1

    @staticmethod
    async def export_nodes_to_xml(server, nodes):
        exporter = XmlExporter(server)
        await exporter.build_etree(nodes)
        await exporter.write_xml("Edge_Server1.xml")


class Alarm:
    @staticmethod
    async def create_alarm(server):
        temp_alarm = await server.get_event_generator()
        temp_alarm.Severity = 300
        return temp_alarm


async def main():
    server, server_idx = await EdgeServer.init_server()
    sensor_monitor_type = await EdgeServer.create_sensor_monitor_type(
        server, server_idx
    )

    (
        client,
        client_idx,
        temp_sensor,
        data,
        state,
        threshold_high,
        threshold_low,
        data_value,
        state_value,
        threshold_high_value,
        threshold_low_value,
    ) = await SensorClient.init_client()
    sub, handler = await SensorClient.subscribe_to_data_change(client, data)

    (
        temp_sm_1,
        tsm_data1,
        tsm_state1,
        tsm_config1,
        tsm_op_mode1,
        tsm_analyze1,
    ) = await TempMonitor.instantiate_temp_monitor(
        server_idx,
        server,
        sensor_monitor_type,
        data_value,
        state_value,
        threshold_high_value,
        threshold_low_value,
    )
    await TempMonitor.export_nodes_to_xml(
        server,
        [temp_sm_1, tsm_data1, tsm_state1, tsm_config1, tsm_op_mode1, tsm_analyze1],
    )

    temp_alarm = await Alarm.create_alarm(server)

    async with server:
        while True:
            if handler.has_data_changed():
                changed_data = handler.get_changed_data()
                await tsm_data1.write_value(changed_data)
                for temp in changed_data:
                    if temp > threshold_high_value:
                        await temp_alarm.trigger(message="OVERHEAT!")
                        _logger.warning("OVERHEAT!")
                        break
                    elif temp < threshold_low_value:
                        await temp_alarm.trigger(message="OVERCOOL!")
                        _logger.warning("OVERCOOL!")
                        break
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
