#!/usr/bin/env python3
from fauxapi_lib import FauxapiLib
import json
from influxdb import InfluxDBClient
import configparser
import argparse
import os
import threading


class pfSenseInfluxCollector:
	def __init__(self, config_file):
		"""Program to send pfSense information collected from FauxAPI to InfluxDB"""
		self.config = configparser.ConfigParser()
		self.config.read(config_file)
		self.fauxapi = FauxapiLib(self.config['FAUXAPI']['APIHost'], self.config['FAUXAPI']['APIKey'], self.config['FAUXAPI']['APISecret'])
		self.influx_client = InfluxDBClient(host=self.config['INFLUXDB']['InfluxDBHost'], port=self.config['INFLUXDB']['Port'],
			username=self.config['INFLUXDB']['Username'], password=self.config['INFLUXDB']['Password'], database=self.config['INFLUXDB']['Database'])
		self.pfSense_config = self.fauxapi.config_get()
		self.pfSense_host = self.pfSense_config['system']['hostname'] + "." + self.pfSense_config['system']['domain']

	def run(self):
		"""Run enabled modules wuth delay as defined in config file"""
		threading.Timer(int(self.config['GENERAL']['Delay']), self.run).start()
		for function in self.module_dictionary:
			if self.config['MODULES'].getboolean(function):
				self.module_dictionary[function](self)

	def fauxapi_function_call(self, functionName):
		"""Call fauxapi function_call without function arguments"""
		data = {
			"function": functionName
		}
		return self.fauxapi.function_call(data)['data']['return']

	def fauxapi_function_call_args(self, functionName, args):
		"""Call fauxapi function_call function with arguments"""
		data = {
			"function": functionName,
			"args": args
		}
		return self.fauxapi.function_call(data)['data']['return']

	def write_influxdb_data(self, data):
		"""Write set of data to InfluxDB."""
		self.influx_client.write_points(data)

	def gateway_status(self):
		"""Get and save information about statuses of gateways."""
		gateways = self.fauxapi_function_call_args("return_gateways_status", "true")
		for gateway in gateways:
			gateway_status = 1 if gateways[gateway]['status'] == "none" else 0
			gateway_data = [
				{
					"measurement": "gateway_status",
					"fields": {
						"name": gateways[gateway]['name'],
						"rtt": gateways[gateway]['delay'],
						"rttsd": gateways[gateway]['stddev'],
						"status": gateway_status
					},
					"tags": {
						"host": self.pfSense_host
					}
				}
			]
			self.write_influxdb_data(gateway_data)

	def interface_statistics(self):
		"""Get and save information about interfaces statistics."""
		interface_descriptions = self.fauxapi_function_call("get_configured_interface_with_descr")
		for interface in interface_descriptions:
			interface_info = self.fauxapi_function_call_args("get_interface_info", interface)
			interface_data = [
				{
					"measurement": "interface_statistics",
					"fields": {
						"bytes_in": interface_info['inbytes'],
						"bytes_out": interface_info['outbytes'],
						"collisions": interface_info['collisions'],
						"errors_in": interface_info['inerrs'],
						"errors_out": interface_info['outerrs'],
						"name": interface_descriptions[interface],
						"packets_in": interface_info['inpkts'],
						"packets_out": interface_info['outpkts']
					},
					"tags": {
						"host": self.pfSense_host,
						"interface": interface_info['if']
					}
				}
			]
			self.write_influxdb_data(interface_data)

	def interface_status(self):
		"""Get and save information about statuses of interfaces."""
		interface_descriptions = self.fauxapi_function_call("get_configured_interface_with_descr")
		for interface in interface_descriptions:
			interface_info = self.fauxapi_function_call_args("get_interface_info", interface)
			interface_data = [
				{
					"measurement": "interface_status",
					"fields": {
						"ip_address": interface_info['ipaddr'],
						"name": interface_descriptions[interface],
						"status": 1 if interface_info['status'] == 'up' else 0
					},
					"tags": {
						"host": self.pfSense_host,
						"interface": interface_info['if']
					}
				}
			]
			self.write_influxdb_data(interface_data)

	def openvpn_client_status(self):
		"""Get and save information about OpenVPN clients."""
		for client in self.fauxapi_function_call("openvpn_get_active_clients"):
			client_data = [
				{
					"measurement": "openvpn_client_status",
					"fields": {
						"remote_host": client['remote_host'],
						"status": 1 if client['status'] == "up" else 0,
						"virtual_address": client['virtual_addr']
					},
					"tags": {
						"host": self.pfSense_host,
						"vpnid": int(client['vpnid']),
					}
				}
			]
			self.write_influxdb_data(client_data)

	def openvpn_connected_clients(self):
		"""Get and save information about connected clients to OpenVPN server."""
		for server in self.fauxapi_function_call("openvpn_get_active_servers"):
			server_name = server['name']
			for connection in server['conns']:
				connection_data = [
					{
						"measurement": "openvpn_connected_clients",
						"fields": {
							"client_id": int(connection['client_id']),
							"common_name": connection['common_name'],
							"remote_host": connection['remote_host'],
							"virtual_address": connection['virtual_addr']
						},
						"tags": {
							"host": self.pfSense_host,
							"server": server_name
						}
					}
				]
				self.write_influxdb_data(connection_data)
			connected_clients_data = [
				{
					"measurement": "openvpn_connected_clients",
					"fields": {
						"connected_clients": len(server['conns'])
					},
					"tags": {
						"host": self.pfSense_host,
						"server": server_name
					}
				}
			]
			self.write_influxdb_data(connected_clients_data)

	def services_status(self):
		"""Get and save information about statuses of services."""
		for service in self.fauxapi_function_call("get_services")[1:]:
			service_status = self.fauxapi_function_call_args("get_service_status", [service])
			service_data = [
				{
					"measurement": "services_status",
					"fields": {
						"description": service['description'],
						"status": 1 if service_status else 0
					},
					"tags": {
						"host": self.pfSense_host,
						"service": service['name']
					}
				}
			]
			self.write_influxdb_data(service_data)

	# Module Dictionary to allow dynamic calling of functions depending on config file
	module_dictionary = {"Gateway_Status": gateway_status, "Interface_Statistics": interface_statistics,
		"Interface_Status": interface_status, "OpenVPN_Client_Status": openvpn_client_status, "OpenVPN_Connected_Clients": openvpn_connected_clients,
		"Services_Status": services_status}


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="A program to send pfSense information to InfluxDB")
	parser.add_argument('--config', default=os.path.dirname(os.path.realpath(__file__)) + '/settings.conf',
		dest='config', help='Use a different location and/or name for the config file')
	args = parser.parse_args()
	collector = pfSenseInfluxCollector(args.config)
	collector.run()
