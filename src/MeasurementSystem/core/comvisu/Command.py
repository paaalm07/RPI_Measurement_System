from __future__ import annotations

import re
from typing import Union, overload


class Command:
    """
    A class representing a ComVisu compatible command to be sent to a server.

    :class:`Command` provides a standardized way to construct and serialize commands for transmission to a server.

    :Init Option1: :class:`Command()` creates an empty Command instance.
    :Init Option2: :class:`Command(cmd_string)` creates a Command instance from a string.
    :Init Option3: :class:`Command(channel,type,value)` creates a Command instance from the given arguments.
    :Init Option4: :class:`Command(channel=channel,type=type,value=value)` creates a Command instance from the given keyword arguments.

    :raises ValueError: If the arguments are invalid.
    :return: A new instance of the Command class or one of its subclasses.
    :rtype: Command
    """

    class Type:
        """
        :class:`Type` provides valid data types for Command.Type.
        """

        FLOAT = "F"
        F = FLOAT
        STRING = "S"
        S = STRING

        @classmethod
        def valid_types(cls):
            return set(vars(cls).values())

        def __contains__(self, item):
            return item in self.valid_types()

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 and len(kwargs) == 0:
            instance = super(Command, cls).__new__(_StringBasedCommand)
            instance.__init__()

        elif len(args) == 1 and len(kwargs) == 0:
            instance = super(Command, cls).__new__(_StringBasedCommand)
            instance.__init__(*args)

        elif len(args) == 0 and len(kwargs) == 3:
            if "channel" not in kwargs or "type" not in kwargs or "value" not in kwargs:
                raise ValueError(
                    "Invalid arguments for ParameterizedCommand: All parameters 'channel', 'type', and 'value' must be set (not None)"
                )
            instance = super(Command, cls).__new__(_ParameterizedCommand)
            instance.__init__(**kwargs)

        elif len(args) == 3 and len(kwargs) == 0:
            if args[0] is None or args[1] is None or args[2] is None:
                raise ValueError(
                    "Invalid arguments for ParameterizedCommand: All parameters 'channel', 'type', and 'value' must be set (not None)"
                )
            instance = super(Command, cls).__new__(_ParameterizedCommand)
            instance.__init__(*args)

        else:
            raise ValueError(
                "Invalid argument count for Command: use  'Command()'  OR  'Command(cmd_string)'  OR  Command(channel, type, value)"
            )

        # Initialize values
        instance.channel = None
        instance.type = None
        instance.value = None

        return instance

    @overload
    def __init__(self) -> None: ...

    @overload
    def __init__(self, cmd_string: str) -> None: ...

    @overload
    def __init__(self, channel: int, type: Type, value: Union[int, float, str]) -> None: ...

    def __init__(self, *args, **kwargs) -> None: ...

    def _apply_values(self, channel, type, value) -> None:
        """
        Check if the given values are valid for a Command instance and set them accordingly.

        :param channel: The channel number to use for the command. Must be an integer between 0 and 999.
        :type channel: int
        :param type: The type of the command. Must be an instance of Type.
        :type type: Type
        :param value: The value of the command. Must be a string or a number.
        :type value: Union[int, float, str]
        :raises ValueError: If any value is invalid.
        :return: None
        :rtype: None
        """

        try:
            channel = int(channel)
            if channel < 0 or channel > 999:
                raise ValueError("Wrong channel number: only 0 to 999 is allowed")
        except:
            raise ValueError("Wrong value for 'channel': only int is allowed")

        if type not in Command.Type():
            raise ValueError(
                f"Wrong value for 'type': only '{Command.Type.FLOAT}' or '{Command.Type.STRING}' is allowed"
            )

        if type == Command.Type.FLOAT:  # and not isinstance(value, int) and not isinstance(value, float):
            try:
                value = float(value)
            except:
                raise ValueError("Wrong value for 'value': only int or float is allowed")

        if type == Command.Type.STRING:
            value = str(value)
            # check for forbidden characters # and ;
            if "#" in value or ";" in value:
                raise ValueError("Forbidden characters in 'value': '#' or ';' are not allowed")

        cmd_string = f"#{channel}{type}{value};"

        if (
            len(cmd_string) > 255
        ):  # 256 is max. command length but there is an option to prefix with '/' for a passive command
            raise ValueError(f"Command in total too long: max. 255 characters. Actual {len(cmd_string)} characters.")

        # Apply values
        self.channel = channel
        self.type = type
        self.value = value

    def _parse_command_string(self, cmd_string) -> None:
        """
        Parse a command string to channel, type and value and apply them to the Command instance accordingly.

        :param cmd_string: The command string to parse.
        :type cmd_string: str
        :raises ValueError: If the command string is invalid.
        :return: None
        :rtype: None
        """

        match = re.match(r"#(\d{1,3})([FS])(.+);", cmd_string)
        if match:
            channel = int(match.group(1))
            type = match.group(2)

            if type == Command.Type.FLOAT:
                value = float(match.group(3))
            else:
                value = match.group(3)

            self._apply_values(channel, type, value)

        else:
            raise ValueError("Invalid command received")

    def to_string(self) -> str:
        """
        :return: Command representation as a string
        :rtype: str
        """

        return f"#{self.channel}{self.type}{self.value};"


class _StringBasedCommand(Command):
    """
    A base class representing a command with string-based arguments. This class is used by the :class:`Command` class when only a `command string` is provided.

    :param cmd_string: The command string to parse. If None or empty, the object is initialized with empty fields.
    :type cmd_string: str

    :return: Command object
    :rtype: Command
    """

    def __init__(self, cmd_string=None):
        super().__init__()

        if cmd_string is not None and cmd_string != "":
            self._parse_command_string(cmd_string)


class _ParameterizedCommand(Command):
    """
    A base class representing a command with parameterized arguments. This class is used by the :class:`Command` class when `channel`, `type` and `value` are provided.

    :param channel: The channel number to use for the command. Must be an integer between 0 and 999.
    :type channel: int
    :param type: The type of the command. Must be an instance of Type.
    :type type: Type
    :param value: The value of the command. Must be a string or a number.
    :type value: Union[int, float, str]

    :return: Command object
    :rtype: Command
    """

    def __init__(self, channel, type, value):
        super().__init__()
        self._apply_values(channel, type, value)


if __name__ == "__main__":

    def test__cmd_string(cmd, expexted_fail):
        print(f"Test: {cmd}         Expected Fail: {expexted_fail}")
        try:
            command = Command(cmd_string=cmd)
            fail = False
        except Exception as e:
            fail = True
            print("    Result:", e)

        if expexted_fail == fail:
            print("    PASS")
            return True
        print("    FAIL <---- FAIL <---- FAIL")
        return False

    # allowed
    test__cmd_string("#0F12.3;", expexted_fail=False)
    test__cmd_string("#0S12.3;", expexted_fail=False)
    test__cmd_string("#0SASDF;", expexted_fail=False)
    test__cmd_string("#999F12.3;", expexted_fail=False)
    test__cmd_string("#999S12.3;", expexted_fail=False)

    test__cmd_string("#999SASDF;", expexted_fail=False)

    # not allowed
    test__cmd_string("#1234X12.3;", expexted_fail=True)  # No Format found
    test__cmd_string("#1234F12.3;", expexted_fail=True)  # Unknown channel format
    test__cmd_string("#xF12.3;", expexted_fail=True)  # Unknown channel format
    test__cmd_string("#0FASDF;", expexted_fail=True)  # Value Error

    print("-------------------------------------------------")

    def test__command_values(channel, type, value, expexted_fail):
        print(f"Test:  Channel: {channel}, Type: {type}, Value: {value}         Expected Fail: {expexted_fail}")
        try:
            cmd = Command(channel=channel, type=type, value=value)
            fail = False
        except Exception as e:
            fail = True
            print("    Result:", e)
        if expexted_fail == fail:
            print("    PASS")
            return True
        print("    FAIL <---- FAIL <---- FAIL")
        return False

    # allowed
    test__command_values(0, Command.Type.FLOAT, 12.3, expexted_fail=False)
    test__command_values("0", Command.Type.STRING, 12.3, expexted_fail=False)
    test__command_values(0, Command.Type.STRING, "asdf", expexted_fail=False)
    test__command_values(999, Command.Type.FLOAT, 12.3, expexted_fail=False)
    test__command_values(999, Command.Type.STRING, 12.3, expexted_fail=False)
    test__command_values("999", Command.Type.STRING, "asdf", expexted_fail=False)

    # not allowed
    test__command_values(123, "X", 123, expexted_fail=True)  # No Format found
    test__command_values("1234", Command.Type.FLOAT, 12.3, expexted_fail=True)  # Unknown channel format
    test__command_values("x", Command.Type.FLOAT, "12.3", expexted_fail=True)  # Unknown channel format
    test__command_values(0, Command.Type.FLOAT, "asdf", expexted_fail=True)  # Value Error
    test__command_values(123, Command.Type.STRING, 100 * "asdf", expexted_fail=True)  # String too long
