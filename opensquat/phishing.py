# -*- coding: utf-8 -*-
# Module: phishing.py
"""
openSquat

(c) Andre Tenreiro

* https://github.com/atenreiro/opensquat

software licensed under GNU version 3
"""
import requests
import time
from opensquat import file_input

from colorama import Fore, Style


class Phishing:

    """
    Class Phishing.

    To use:
        Phishing().main(keyword)

    Attribute:
        keyword: list of keywords
    """
    def __init__(self):
        self.phishing_db = "https://phish.co.za" \
                           "/latest/" \
                           "phishing-domains-ACTIVE.txt"
        self.phishing_filename = "phishing.db"
        self.keyword = ""
        self.keywords_filename = ""
        self.list_domains = []
        self.keywords_total = 0

    def set_keywords(self, keywords):
        self.keywords_filename = keywords

    @staticmethod
    def URL_contains(keyword, phishing):
        if keyword in phishing:
            return True

        return False

    def count_keywords(self):
        self.keywords_total = file_input.InputFile().main(
            self.keywords_filename,
            None
            )

    def check_phishing(self):
        # keyword iteration
        i = 0

        # Open phishing DB
        with open(self.keywords_filename, mode='r', encoding='utf-8') as f_key:
            for raw_keyword in f_key:
                keyword = raw_keyword.strip().lower()

                # Skip blank, whitespace-only, and comment lines. Replaces
                # the old line[0] indexing pattern that crashed on empty
                # input and also miscounted whitespace-only lines.
                if not keyword or keyword.startswith("#"):
                    continue

                i += 1
                print(
                    Fore.WHITE + "\n[*] Verifying keyword:",
                    keyword,
                    "[",
                    i,
                    "/",
                    self.keywords_total,
                    "]" + Style.RESET_ALL,
                )

                with open(self.phishing_filename, mode='r', encoding='utf-8') as f_phishing:
                    for site in f_phishing:
                        # Lowercase AND strip newline in one pass. The old
                        # version assigned site.lower() then overwrote it
                        # with site.replace("\n", ""), producing a case-
                        # sensitive comparison that missed mixed-case hits.
                        phishing_site = site.replace("\n", "").lower()

                        if self.URL_contains(keyword, phishing_site):
                            print(
                                Style.BRIGHT + Fore.YELLOW +
                                "  \\_ Similarity detected between",
                                keyword,
                                "and",
                                phishing_site,
                                "" + Style.RESET_ALL
                                )
                            self.list_domains.append(phishing_site)

        return self.list_domains

    def update_db(self):

        try:
            print(
                "[*] Downloading fresh Phishing DB from",
                self.phishing_db
                )
            session = requests.session()
            # Add timeout so a hung phishing DB server cannot freeze the CLI.
            r = session.get(self.phishing_db, timeout=60)

            data = r.content
            r.close()
            session.close()

            # Get reported size from header, but fall back to the actual
            # body length when the header is missing (chunked encoding).
            # Without this fallback, a chunked response with no
            # Content-Length was incorrectly treated as "file not found"
            # even when the body had valid data — same bug that was
            # already fixed in feed_manager.py.
            total_size = int(r.headers.get("content-length", 0))
            if total_size == 0:
                total_size = len(data)

            total_size_mb = round(float(total_size / 1024 / 1024), 2)

            if total_size == 0:
                print(
                    "[ERROR] File not found or empty! Contact the authors " +
                    "or try again later. Exiting...\n",
                )
                exit(-1)

            print("[*] Download volume:", total_size_mb, "MB")

            with open(self.phishing_filename, "wb") as f:
                f.write(data)

        except requests.exceptions.RequestException:
            print("")
            exit(-1)

        return True

    def main(self, keywords):
        """
        main function that will call other functions.

        Args:
            keyword: keyword to search for(duh)

        Return:
            none
        """
        print("")
        print("+---------- Checking Phishing sites ----------+")
        time.sleep(2)
        self.set_keywords(keywords)
        self.update_db()
        self.count_keywords()
        return self.check_phishing()
