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


@uamethod
def temp_data_preprocess(parent, data):
    mean = statistics.mean(data)
    std_deviation = statistics.stdev(data)

    return mean, std_deviation


async def main():
    """
    Server initialize goes first
    """

    server = Server()
    await server.init()

    server.set_endpoint("opc.tcp://localhost:4860/freeopcua/edge/")
    server.set_server_name("Edge_Server1")
    server.set_security_policy(
        [
            ua.SecurityPolicyType.NoSecurity,
            ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            ua.SecurityPolicyType.Basic256Sha256_Sign,
        ]
    )

    uri = "http://sample.sensor2hmi.io"
    idx = await server.register_namespace(uri)
    _logger.warning(f"Server Namespace index: {idx}")

    # create sensor-monitor node type
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

    """
    Client connection goes second
    """

    async with Client(url="opc.tcp://localhost:4850/freeopcua/temp_sensor1/") as client:
        _logger.warning("Root node is: %r", client.nodes.root)
        _logger.warning(
            "Children of root are: %r", await client.nodes.root.get_children()
        )

        uri = "http://sample.sensor2hmi.io"
        idx = await client.get_namespace_index(uri)
        _logger.warning(f"Client Namespace index: {idx}")

        # get node from Temperature Sensor
        temp_sensor = client.get_node(ua.NodeId(5, 2))
        data = client.get_node(ua.NodeId(7, 2))
        state = client.get_node(ua.NodeId(8, 2))
        threshold_high = client.get_node(ua.NodeId(9, 2))
        threshold_low = client.get_node(ua.NodeId(10, 2))

        # subscribe to data change
        handler = SubHandler()
        sub = await client.create_subscription(50, handler)
        handle = await sub.subscribe_data_change(data)
        # await sub.unsubscribe(handle)
        # await asyncio.sleep()

        # subscribe to events
        await sub.subscribe_events()

        # read value of node
        data = copy.copy(await data.read_value())
        state = copy.copy(await state.read_value())
        threshold_high = copy.copy(await threshold_high.read_value())
        threshold_low = copy.copy(await threshold_low.read_value())

        """
        instantiate server nodes depending on client-connection
        """

        # instantiate Temperature_sensor1 monitor node
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

        # create event (just for testing purpose)
        temp_alarm = await server.get_event_generator()
        temp_alarm.Severity = 300

        # export nodes to xml
        exporter = XmlExporter(server)
        await exporter.build_etree(
            [
                temp_sm_1,
                tsm_data1,
                tsm_state1,
                tsm_config1,
                tsm_op_mode1,
                tsm_analyze1,
            ]
        )
        await exporter.write_xml("Edge_Server1.xml")

        """
        start Server
        """

        async with server:
            """
            looping task execution goes last
            """

            while True:
                # check data from sensor
                if handler.has_data_changed():
                    changed_data = handler.get_changed_data()
                    await tsm_data1.write_value(changed_data)
                    for temp in changed_data:
                        if temp > threshold_high:
                            await temp_alarm.trigger(message="OVERHEAT!")
                            _logger.warning("OVERHEAT!")
                            break
                        elif temp < threshold_low:
                            await temp_alarm.trigger(message="OVERCOOL!")
                            _logger.warning("OVERCOOL!")
                            break
                await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
