# -*- coding: utf-8 -*-
# Module: output.py
"""
openSquat

(c) Andre Tenreiro

* https://github.com/atenreiro/opensquat

software licensed under GNU version 3
"""
import json
import csv
from datetime import date


class SaveFile:

    """
    The SaveFile is responsible for the file saving operations.

    To use:
        Domain().main(keywords, confidence, domains)

    Attribute:
        type: file type (txt, csv, json)
        today: today's date in the format yyyy-mm-dd
        filename: output file name
        content: file content to be saved
    """

    def __init__(self):
        self.type = None
        self.today = date.today().strftime("%Y-%m-%d")
        self.filename = None
        self.content = []

    def as_json(self):
        """
        save to json.

        Args:
            none

        Return
            none
        """
        with open(self.filename, "w", encoding='utf-8') as f_json:
            json.dump(self.content, f_json, indent=2, ensure_ascii=False)

    def as_csv(self):
        """
        Save to CSV.

        self.content must be a list of rows, where each row is a list
        of column values. The first row is treated as the header.

        Written with a UTF-8 BOM so Excel on Windows correctly detects
        the encoding when cells contain unicode characters (e.g. the
        homograph renderings in the `unicode` column from Premium API
        mode). Linux/macOS tools and Python's csv.reader ignore the BOM
        on read.

        newline='' is the stdlib-recommended way to open a file for
        csv.writer; without it, csv doubles line endings on Windows.
        """
        with open(self.filename, "w", encoding='utf-8-sig', newline='') as f_csv:
            writer = csv.writer(
                f_csv, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            writer.writerows(self.content)

    def as_text(self):
        """
        save to plain text.

        Args:
            none

        Return
            none
        """
        with open(self.filename, "w", encoding='utf-8') as f:
            for item in self.content:
                f.write(item + "\n")
        f.close()

    def set_content(self, file_content):
        self.content = file_content

    def set_filename(self, file_name):
        self.filename = file_name

    def set_filetype(self, file_type):
        self.type = file_type

    def main(self, file_name, file_type, file_content):
        """
        main function that will call other functions.

        Args:
            file_name: file name (duh)
            file_type: file type (txt, json or csv)
            file_content: file content to be saved

        Return:
            none
        """
        self.set_filename(file_name)
        self.set_filetype(file_type)
        self.set_content(file_content)

        if file_type == "json":
            self.as_json()
        elif file_type == "csv":
            self.as_csv()
        else:
            self.as_text()
