import asyncio
from asyncua import Client

# Define the server URL and namespace
url = "opc.tcp://localhost:4840/freeopcua/server/"
namespace = "http://examples.freeopcua.github.io"


async def main():
    # Connect to the OPC UA server
    print(f"Connecting to {url} ...")
    async with Client(url=url) as client:
        # Find the namespace index
        nsidx = await client.get_namespace_index(namespace)
        print(f"Namespace Index for '{namespace}': {nsidx}")

        # Define the path to the variable node for read / write
        path = ["0:Objects", f"{nsidx}:temp_sensor", f"{nsidx}:temp"]

        # Get the variable node
        var = await client.nodes.root.get_child(path)

        # Read the current value of the variable
        value = await var.read_value()
        print(f"Value of temp ({var}): {value}")

        # Continually call a method on the server as fast as possible
        while True:
            res = await client.nodes.objects.call_method(
                f"{nsidx}:temprature_check", value
            )
            print(f"Calling ServerMethod returned {res}")


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
