import asyncio
import logging
import numpy as np

from asyncua import Server, ua
from asyncua.common.methods import uamethod
from asyncua.common.xmlexporter import XmlExporter


# Define a method to be used by the server
@uamethod
def func(parent, temp):
    # Check the temperature and return a warning message if necessary
    if temp > 28:
        return "overheating warning"
    elif temp < 22:
        return "overcooling warning"
    else:
        return "temperature is within acceptable range"

async def main():
    # Initialize the logger
    _logger = logging.getLogger(__name__)
    
    # Initialize the server
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    
    # Register a namespace
    uri = "http://examples.freeopcua.github.io"
    idx = await server.register_namespace(uri)
    
    # Add an object to the server with a variable
    myobj = await server.nodes.objects.add_object(idx, "temp_sensor")
    myvar = await myobj.add_variable(idx, "temp", 25.0)
    
    # Make the variable writable
    await myvar.set_writable()
    
    # Add a method to the server
    await server.nodes.objects.add_method(
        ua.NodeId("temprature_check", idx),
        ua.QualifiedName("temprature_check", idx),
        func,
        [ua.VariantType.Int64],
        [ua.VariantType.Int64],
    )
    
    _logger.info("Starting server!")
    
    # Export the server configuration to an XML file
    exporter = XmlExporter(server)
    await exporter.build_etree([myobj])
    xml_string = await exporter.write_xml('C:/Python_projects/test.xml')
    _logger.info("xml string: %s", xml_string)
    
    # Start the server and continuously update the temperature value
    async with server:
        while True:
            await asyncio.sleep(1)
            
            # Generate a new temperature value
            new_temp = np.random.normal(await myvar.get_value(), 3, 1000)
            new_temp = np.clip(new_temp, 18, 32)                        
            
            _logger.info("Random temp value %s is %.1f", myvar, np.random.choice(new_temp))
            await myvar.write_value(np.random.choice(new_temp))
            
if __name__ == "__main__":
    # Set the logging level and start the server
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(), debug=True)