import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from scapy.all import *
from scapy.layers.inet import TCP, IP


class PacketAnalyzer:
    """Class for analyzing packets."""

    def __init__(self, packets):
        """Initialize the PacketAnalyzer."""
        self.packets = packets
        self.seq_to_time = {}  # Mapping sequence numbers to their corresponding times
        self.one_second_packets = []  # Storing packets within one second
        self.packets_with_rtt = {}  # Mapping packets to their RTTs
        self.current_packet_index = 0  # Keeping track of current packet

    def calculate_total_throughput(self):
        """Calculate total throughput from packets."""
        return sum(len(self.packets[packet_index]) for packet_index in self.one_second_packets)

    def calculate_average_rtt(self):
        """Calculate the average RTT."""
        rtt_values = [
        self.packets_with_rtt[pkt_index]
        for pkt_index in self.one_second_packets
        if pkt_index in self.packets_with_rtt and self.packets_with_rtt[pkt_index] is not None
        ]
        return sum(rtt_values) / len(rtt_values) if rtt_values else None

    def calculate_rtt(self):
        """Calculate RTT for packets and update seq_to_time and packets_with_rtt."""
        for index, pkt in enumerate(self.packets):
            if IP in pkt and TCP in pkt:
                seq = pkt[TCP].seq
                ack = pkt[TCP].ack
                rtt = pkt.time - self.seq_to_time[ack] if pkt[TCP].flags == "A" and ack in self.seq_to_time else None
                if pkt[TCP].flags in ["PA", "P"]:
                    self.seq_to_time[seq + len(pkt[TCP].load)] = pkt.time
                self.packets_with_rtt[index] = rtt

    def calculate_retransmission_rate(self):
        """Calculate retransmission rate for packets."""
        total_packet_count = len(self.one_second_packets)
        retransmission_count = 0
        expected_seq = {}

        for packet_index in self.one_second_packets:
            packet = self.packets[packet_index]
            if TCP not in packet:
                continue
            if Raw in packet[TCP]:
                data_len = len(packet[TCP].load)
            else:
                data_len = 0

            syn_flag, fin_flag = packet[TCP].flags.S, packet[TCP].flags.F
            if data_len > 0 or syn_flag or fin_flag:
                if packet[TCP].seq in expected_seq and expected_seq[packet[TCP].seq] > packet[TCP].seq:
                    retransmission_count += 1
                expected_seq[packet[TCP].seq] = packet[TCP].seq + data_len

        return retransmission_count / total_packet_count if total_packet_count > 0 else 0  # Handle division by zero

    def process_packets(self):
        """Process packets and yield a dictionary of results."""
        self.calculate_rtt()
        while self.current_packet_index < len(self.packets):
            start_time = self.packets[self.current_packet_index].time
            self.one_second_packets = []

            while self.current_packet_index < len(self.packets) and self.packets[self.current_packet_index].time < start_time + 1:
                self.one_second_packets.append(self.current_packet_index)
                self.current_packet_index += 1

            yield {
                "Total Throughput": self.calculate_total_throughput(),
                "Average RTT": self.calculate_average_rtt(),
                "Retransmission Rate": self.calculate_retransmission_rate(),
            }


def analyze_pcap_files():
    """Analyze .pcapng files in the current directory and write results to a .xlsx file."""
    pcapng_files = [f for f in os.listdir(".") if os.path.isfile(f) and f.endswith(".pcapng")]

    wb = Workbook()

    for pcapng_file in pcapng_files:
        packets = rdpcap(pcapng_file)
        packet_analyzer = PacketAnalyzer(packets)
        df = pd.DataFrame(packet_analyzer.process_packets())
        df.to_csv(pcapng_file + ".csv", index=False)
        ws = wb.create_sheet(pcapng_file)

        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)

    wb.save("Compilation.xlsx")


if __name__ == "__main__":
    analyze_pcap_files()
