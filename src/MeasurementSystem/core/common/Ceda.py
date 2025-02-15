from __future__ import annotations

import logging
import os
import time
import warnings
from typing import overload

import numpy as np
import pandas as pd

logger = logging.getLogger("Ceda")
logger.setLevel(logging.DEBUG)


class Ceda:
    """Output Manager (Ceda Style)
    Wrapper of a pandas DataFrame to provide a LabVIEW Modular Sequencer style output (Ceda)
    and its functionality during automation like duprow
    """

    def __init__(self, data_dict={}):
        """
        :param dict data_dict: new value of Dataframe
            if type is a dictionary, format has to be strictly {column_name: list(values), ...}
        """
        self._df = pd.DataFrame(data_dict)

        # print all columns using 'print' function
        pd.set_option("display.max_columns", None)

        # to avoid future warnings in ffill() function
        pd.set_option("future.no_silent_downcasting", True)

    @property
    def data(self) -> pd.DataFrame:
        return self._df

    @data.setter
    def data(self, val) -> None:
        """Create a new DataFrame (overwrite!)
        :param DataFrame/dict val: new value of Dataframe
            if type is a dictionary, format has to be strictly {column_name: list(values), ...}
        """
        if isinstance(val, pd.DataFrame):
            self._df = val
        elif isinstance(val, dict):
            self._df = pd.DataFrame(val)
        else:
            raise ValueError("Invalid value for data")

    @overload
    def append(self, column_name: str, value: any) -> None:
        """Append a value to a specific column of the DataFrame
        :param column_name: Column name
        :param type: str
        :param value: value
        :param type: any
        """

    @overload
    def append(self, dictionary: dict) -> None:
        """Append a dictionary to the DataFrame
        :param dictionary: Dictionary to be added
        :param type: dict
        """

    def append(self, *args: str | dict | any) -> None:
        if len(args) == 2 and isinstance(args[0], str):
            self._append_columnname_value(args[0], args[1])
        elif len(args) == 1 and isinstance(args[0], dict):
            self._append_dictionary(args[0])
        else:
            raise TypeError("Invalid arguments for append method")

    def _append_columnname_value(self, column_name, value) -> None:
        """Append a value to a specific column of the DataFrame
            If column does not exist: it will be created
            If column already exist: a new row will be added
            New rows has values NaN
        :param str column_name: Column name
        :param any value: Value
        """

        if self._df.empty:
            # DataFrame is empty, insert new column and value as the first row
            self._df[column_name] = pd.Series([value], dtype=object)
        elif column_name in self._df.columns:
            # Column already exists
            last_row_index = self._df.index[-1]
            last_value = self._df.loc[last_row_index, column_name]
            if pd.isnull(last_value):
                # Last value is NaN, overwrite it
                self._df.loc[last_row_index, column_name] = value
            else:
                # Create a new row
                new_row = pd.Series([np.nan] * len(self._df.columns), index=self._df.columns, dtype=object)
                new_row[column_name] = value
                new_df = pd.DataFrame([new_row])
                self._df = pd.concat([self._df, new_df], ignore_index=True)
        else:
            # Column does not exist, insert at the end and add value to the last existing row
            self._df[column_name] = pd.Series([np.nan] * len(self._df), dtype=object)
            last_row_index = self._df.index[-1]
            self._df.loc[last_row_index, column_name] = value

    def _append_dictionary(self, dictionary) -> None:
        """Append a Dictionary to the DataFrame
        :param dict dictionary: Dictionary to be appended
        """
        if not isinstance(dictionary, dict):
            raise ValueError("Invalid value for dictionary. Expected a dictionary.")

        for key, value in dictionary.items():
            self.append(key, value)

    def log(self, columnName, message, newLine=False) -> None:
        """Add a message to a specific column
        :param str  columnName: column name
        :param str  message: message text
        :param bool newLine: if True and log message will be created in a new line of the DataFrame
        """

        if columnName in self._df.columns:
            if newLine:
                self.append(columnName, message)
            else:
                # add message to existing text of Log column
                self._df.tail(1)[columnName] += "; " + message
        else:
            # Log columns does not exists
            if newLine:
                self.duprow()
                self.append(columnName, message)
            else:
                self.append(columnName, message)

    def save(
        self,
        filePath=r"C:\UserData\results.csv",
        overwrite: bool = False,
        print_index: bool = True,
        fill_nan_values: bool = False,
        nan_replacement: str = "=NA()",
    ) -> None:
        """Save DataFrame to CSV File
        :param file: (optional) Path to CSV File, default "C:\\UserData\\results.csv"
        :type file: str
        :param overwrite: (optional) if True, overwrite existing file, otherwise add timestamp to existing file, default False
        :type overwrite: bool
        :param print_index: (optional) if True, output also index column, default True
        :type print_index: bool
        :param fill_nan_values: (optional) if True, fill NaN values with previous row value (if no previous row exists, NaN is used), default False
        :type fill_nan_values: bool
        :param nan_replacement: (optional) value to replace NaN values, default "=NA()"
        :type nan_replacement: str
        """

        if not overwrite and os.path.isfile(filePath):
            # File already exists and overwrite is False
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_filename, ext = os.path.splitext(filePath)
            new_file = f"{base_filename}_{timestamp}{ext}"
            print(f"File '{filePath}' already exists. Saving as '{new_file}' instead.")
            filePath = new_file

        if fill_nan_values:
            # fill NaN with previous row value
            # if no previous row exists, value is NaN
            df_copy = self._df.ffill().replace(np.nan, nan_replacement)
        else:
            # Replace NaN values with nan_replacement argument
            df_copy = self._df.replace(np.nan, nan_replacement)

        # Check if directory exists
        directory = os.path.dirname(filePath)
        try:
            os.makedirs(directory)
        except FileExistsError:
            pass

        # Save DataFrame to CSV with ';' as the separator
        try:
            df_copy.to_csv(filePath, sep=";", index=print_index)
        except PermissionError:
            base_filename, ext = os.path.splitext(filePath)
            new_file = f"{base_filename}_copy{ext}"
            print(
                f"File '{filePath}'seems to be blocked or there are no sufficient permissions - wirte {new_file} instead"
            )
            df_copy.to_csv(new_file, sep=";", index=print_index)
        except Exception as e:
            print("ERROR")
            print(e)

    def load(self, filePath, index_col=None) -> None:
        """Load a CSV File to the DataFrame (overwrite!)
        :param filePath: filePath to CSV file, seperator has to be ";"
        :type filePath: str
        :param index_col: (optional) Column to be used as index, default None
        :type index_col: str
        """
        self._df = pd.read_csv(filePath, sep=";", keep_default_na=False, index_col=index_col)
        self._df = self._df.replace("=NA()", np.nan)

    def clear(self) -> None:
        """Clear the whole DataFrame"""
        self._df = pd.DataFrame()

    def duprow(self) -> None:
        """Duplicate last row and replace entries with NaN"""
        if not self._df.empty:
            last_row = self._df.iloc[-1]
            # self._df = self._df.append(last_row, ignore_index=True)  # Note: append function was removed in pandas !
            new_df = pd.DataFrame([last_row])
            self._df = pd.concat([self._df, new_df], ignore_index=True)
            self._df.iloc[-1] = np.nan  # replace duplicated row with np.Nan

    def delete(self, last_n=1) -> None:
        """Delete the last n rows of the DataFrame
        :param last_n: number of rows to be deleted, defaults to 1
        :type last_n: int
        """
        if not self._df.empty:
            self._df.drop(self._df.tail(last_n).index, inplace=True)

    def merge(self, other: Ceda) -> None:
        """Merge the current Ceda object (self) with another Ceda object
        :param other: the other Ceda object to merge into to current one
        :type other: Ceda

        :raise: ValueError
        """
        if not isinstance(other, Ceda):
            raise ValueError("Invalid value for other. Expected a Ceda object.")

        self._df = pd.concat([self._df, other._df], ignore_index=True)


if __name__ == "__main__":
    # Example of usage
    ceda = Ceda()
    ceda.append("A", 1)
    ceda.append({"B": 2, "A": 3})
    ceda.duprow()

    print(ceda.data)
