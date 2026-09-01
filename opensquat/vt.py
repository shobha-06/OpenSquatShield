# -*- coding: utf-8 -*-
# Module: virustotal.py
"""
openSquat

* https://github.com/atenreiro/opensquat

software licensed under GNU version 3
"""
import os
import json
import requests


class VirusTotal:
    """
    This domain class validates a domain on VirusTotal.

    To use:
        VirusTotal().main("opensquat.com")                     # domain report
        VirusTotal().main("opensquat.com", mode="subdomains")  # subdomain lookup

    Attribute:
        domain: a domain name
    """
    def __init__(self):
        """Initiator."""
        self.domain = ""
        self.api_key = ""
        self.api_key_file = ""

    def set_apikey(self, api_key_file):

        self.api_key_file = api_key_file

        if not os.path.isfile(self.api_key_file):
            print(
                "[*] VT API Key File",
                self.api_key_file,
                "not found or not readable! Exiting... \n",
            )
            exit(-1)

        # Read the first non-blank, non-comment line as the API key.
        # The old version used line[0] indexing (crash on empty lines)
        # and let later lines silently overwrite earlier ones.
        with open(self.api_key_file, mode='r', encoding='utf-8') as file_vt:
            for line in file_vt:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.api_key = line
                    break

        return True

    def set_domain(self, domain):
        self.domain = domain

    def domain_report(self):
        """
        Fetch the VT domain report and return [harmless, malicious].

        Returns:
            list[int]: [harmless_votes, malicious_votes]. Returns [0, -1]
            when VT responds with 200 but the expected data structure is
            missing, so callers can treat the negative malicious value as
            a throttling/failure signal without crashing (fixes #112).
        """
        url = "https://www.virustotal.com/api/v3/domains/" + self.domain

        headers = {
            "accept": "application/json",
            "x-apikey": self.api_key
        }

        response = requests.get(url, headers=headers, timeout=30)

        try:
            json_data = json.loads(response.text)
        except (ValueError, json.JSONDecodeError):
            json_data = {}

        if response.status_code == 200:

            if (
                "data" in json_data
                and "attributes" in json_data['data']
                and "total_votes" in json_data['data']['attributes']
            ):

                harmless = json_data['data']['attributes']['total_votes']['harmless']
                malicious = json_data['data']['attributes']['total_votes']['malicious']
                harmless = int(harmless)
                malicious = int(malicious)
                return [harmless, malicious]

            # 200 OK but data structure is missing — treat as throttled/failed.
            return [0, -1]

        if "error" in json_data:
            message = json_data['error']['message']
            print("[*] VT API ERROR:", message)
            exit(-1)
        else:
            print(
                "[*] Unexpected VT Response. HTTP Code: ",
                response.status_code,
                " Exiting... \n",
            )
            exit(-1)

    def subdomains(self):
        """
        Fetch the list of subdomains of self.domain from VirusTotal.

        Returns:
            list[str]: list of subdomain strings. Returns an empty list
            if VT responds with 200 but the data is missing, or if the
            domain has no known subdomains.
        """
        url = "https://www.virustotal.com/api/v3/domains/" + self.domain + "/subdomains"

        headers = {
            "accept": "application/json",
            "x-apikey": self.api_key
        }

        response = requests.get(url, headers=headers, timeout=30)

        try:
            json_data = json.loads(response.text)
        except (ValueError, json.JSONDecodeError):
            return []

        if response.status_code == 200:
            data = json_data.get("data", [])
            return [item["id"] for item in data if isinstance(item, dict) and "id" in item]

        if "error" in json_data:
            message = json_data['error']['message']
            print("[*] VT API ERROR:", message)
            return []

        print(
            "[*] Unexpected VT Response. HTTP Code: ",
            response.status_code,
            "\n",
        )
        return []

    def main(self, domain, mode="report", api_key_file="vt_key.txt"):
        """
        Run a VirusTotal lookup.

        Args:
            domain: domain to look up
            mode: "report" (default) returns [harmless, malicious] vote
                  counts; "subdomains" returns a list of subdomain strings.
            api_key_file: path to the file containing the VT API key.

        Return:
            list: vote counts (report mode) or subdomain strings.
        """
        self.set_domain(domain)
        self.set_apikey(api_key_file)

        if mode == "subdomains":
            return self.subdomains()
        return self.domain_report()
