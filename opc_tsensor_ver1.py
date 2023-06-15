import asyncio
import copy
import logging
import random

from asyncua import ua, Server
from asyncua.common.xmlexporter import XmlExporter


_logger = logging.getLogger(__name__)


# Subscription Handler. To receive events from server for a subscription
class SubHandler(object):
    def datachange_notification(self, node, val, data):
        _logger.warning("Python: New data change event %s %s", node, val)

    def event_notification(self, event):
        _logger.warning("Python: New event %s", event)


# generate temperature data
def generate_temperature(mu=25, sigma=1, n=100):
    temp_data = []
    for i in range(n):
        temp_data.append(random.normalvariate(mu, sigma))
    return temp_data


async def main():
    server = Server()
    await server.init()

    server.set_endpoint("opc.tcp://localhost:4850/freeopcua/temp_sensor1/")
    server.set_server_name("Temperature_Sensor1")

    server.set_security_policy(
        [
            ua.SecurityPolicyType.NoSecurity,
            ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            ua.SecurityPolicyType.Basic256Sha256_Sign,
        ]
    )

    uri = "http://sample.sensor2hmi.io"
    idx = await server.register_namespace(uri)
    _logger.info(f"Namespace index: {idx}")

    # create sensor node type
    sensor_type = await server.nodes.base_object_type.add_object_type(
        idx, "temp_sensor"
    )
    await (await sensor_type.add_property(idx, "device_id", "A01")).set_modelling_rule(
        True
    )
    await (
        await sensor_type.add_variable(
            idx, "data", ua.Variant([], ua.VariantType.Double)
        )
    ).set_modelling_rule(True)
    await (await sensor_type.add_property(idx, "status", "idle")).set_modelling_rule(
        True
    )

    # instantiate sensor node
    temp_sensor_1 = await sensor_type.add_object(idx, "temp_sensor_1", sensor_type)
    threshold_high_1 = await temp_sensor_1.add_property(idx, "threshold_high", 28.0)
    threshold_low_1 = await temp_sensor_1.add_property(idx, "threshold_low", 22.0)
    data_1 = await temp_sensor_1.get_child(["2:data"])

    # status node now can be written by client
    status_1 = await temp_sensor_1.get_child(["2:status"])
    await status_1.set_writable()

    # export nodes to xml
    exporter = XmlExporter(server)
    await exporter.build_etree(
        [temp_sensor_1, data_1, status_1, threshold_high_1, threshold_low_1]
    )
    await exporter.write_xml("Temperature_Sensor1.xml")

    # create event (just for testing purpose)
    status_change_event = await server.get_event_generator()
    status_change_event.Severity = 300

    # start server
    async with server:
        # create subscription
        handler = SubHandler()
        sub = await server.create_subscription(50, handler)
        # handle = await sub.subscribe_data_change(data_1)
        handle = await sub.subscribe_events()

        while True:
            # update new status
            await status_1.write_value("running")
            await status_change_event.trigger(message="status changed: running")

            # update new temperature data
            temp_data = await data_1.read_value()
            temp_data = copy.copy(temp_data)
            temp_data = generate_temperature()
            await data_1.write_value(temp_data)

            # update new status II
            await status_1.write_value("idle")
            # await status_change_event.trigger(message="status changed: idle")
            await asyncio.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # optional: setup logging
    # logger = logging.getLogger("asyncua.address_space")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.internal_server")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.binary_server_asyncio")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.uaprocessor")
    # logger.setLevel(logging.DEBUG)

    asyncio.run(main())
