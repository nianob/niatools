from __future__ import annotations
import io
import json
import os
import shutil

from typing import overload, Optional, Any, TypedDict, Required, TypeVar, Generic, Literal

# ----------------------------------------------------------------
# Type definitons

_T = TypeVar("_T")

class SettingDict(TypedDict, Generic[_T], total=False):
    default: _T # The default value
    description: str # A description of the setting
    sensititve: bool # Does the setting contain sensitive information, default: false
    value: Required[_T] # What the setting is currently set to

class HiddenObject:
    def __init__(self) -> None: ...
    def __str__(self) -> str: return "<hidden>"
    def __repr__(self) -> str: return "<hidden>"

# ----------------------------------------------------------------
# Main

_global: Optional[Settings] = None

def getGlobal() -> Settings:
    """Returns the global settings
    
    Returns:
        settings: The global settings
    Raises:
        ValueError: There are no global settings defined
    """
    global _global
    if _global is None:
        raise ValueError("There are no global settings defined")
    return _global

class Settings:
    """The settings from a specific file"""

    # ----------------------------------------------------------------
    # init
    @overload
    def __init__(self, filename: str, default: Optional[str] = None, *, isGlobal: bool = False) -> None: ...
    @overload
    def __init__(self, fp: io.IOBase, *, isGlobal: bool = False) -> None: ...
    def __init__(self, *args, **kwargs):
        """loads the settings

        The settings can be loaded by providing 
        either a filename or a file-like object.
        When using a filename another one can be
        specified, which will be used as the fallback
        
        Args:
            filename: the name of the settings file
            default: the name of the fallback file
            fp: the file-like object
        
        Raises:
            FileNotFoundError: The specified file was not found.
            json.JSONDecodeError: The file does not contain valid json.
        """

        # Get the filename if given
        filename_arg: Optional[str] = args[0] if len(args) >= 1 and isinstance(args[0], str) else None
        filename_kwarg: Optional[str] = kwargs.get("filename", None)
        self.filename: Optional[str] = filename_arg or filename_kwarg
        
        # Get the fallback filename if given
        default_arg: Optional[str] = args[1] if len(args) >= 2 and isinstance(args[1], str) else None
        default_kwarg: Optional[str] = kwargs.get("default", None)
        default: Optional[str] = default_arg or default_kwarg

        # Get the file-like object if given
        fp_arg: Optional[io.IOBase] = args[0] if len(args) >= 1 and isinstance(args[0], io.IOBase) else None
        fp_kwarg: Optional[io.IOBase] = kwargs.get("fp", None)
        fp: Optional[io.IOBase] = fp_arg or fp_kwarg

        # Load the Data
        if fp:
            loaded_settings = json.load(fp)
        elif self.filename:
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    loaded_settings = json.load(f)
            elif default:
                with open(default, "r") as f:
                    loaded_settings = json.load(f)
            else:
                raise FileNotFoundError("The config file was not found")
        else:
            raise ValueError("either \"filename\" or \"fp\" must be provided!")

        # Store the data
        self._settings: dict[str, SettingDict] = loaded_settings

        # Set this to the global instance
        if kwargs.get("isGlobal", False):
            global _global
            _global = self

    # ----------------------------------------------------------------
    # general operations
    def get(self, name: str, default: Any = None) -> Any:
        """returns the value of the setting
        
        Args:
            name: The name of the setting
            default: the value to use if the setting does not exisit
        Returns:
            data: The value of the setting
        """
        return self._settings.get(name, {"value": default})["value"]
    
    def set(self, name: str, value: Any) -> None:
        """sets a setting to the given value
        
        Args:
            name: the name of the setting
            value: what the setting should be set to
        """
        setting: SettingDict = self._settings.get(name, {"value": None})
        setting["value"] = value
        self._settings[name] = setting
    
    def getPropety(self, name: str, property: Literal["default", "description", "sensitive", "value"]) -> Any:
        """gets a property of a setting
        
        Args:
            name: the name of the setting
            propetry: which property to get. Can be one of: "default", "description", "sensitive", "value"
        
        Returns:
            data: The property. Defaults to None if the setting doesn't have the property
        
        Raises:
            ValueError: There is no setting with the provided name
        """
        if not name in self._settings:
            raise ValueError(f"there is no setting named \"{name}\"")

        return self._settings[name].get(property, None)

    def reset(self, name: str) -> None:
        """resets a settings
        
        Args:
            name: the name of the setting
        Raises:
            ValueError: This setting has no default value or there is no setting with the provided name
        """
        if not name in self._settings.keys():
            raise ValueError(f"there is no setting named \"{name}\"")
        if not "default" in self._settings[name].keys():
            raise ValueError(f"\"{name}\" has no default setting!")
        self._settings[name]["value"] = self._settings[name].get("default")
    
    # ----------------------------------------------------------------
    # save the settings to file
    def save(self, filename: Optional[str] = None) -> None:
        """Saves the settings to file
        
        Args:
            filename: the name of the settingsfile. Defaults to the one used for loading the settings
        Raises:
            TypeError: there is an unserializeable object in the settings
            ValueError: the location to save the file could not be determined
        """
        # we will write the data to a temporaty file first
        # and then move the file as this ensures that the
        # data cannot be lost when there is an error while
        # writing the file

        # write to a temporary file
        final_filename = filename or self.filename

        if not final_filename:
            raise ValueError("Location to save the file is unknown")

        directory, name = os.path.split(final_filename)
        tmp_path = os.path.join(directory, f"tmp_{name}")

        with open(tmp_path, "w+") as f:
            json.dump(self._settings, f)

        # replace the old file
        shutil.copyfile(tmp_path, final_filename)
        os.remove(tmp_path)
    
    # ----------------------------------------------------------------
    # python internals to allow for stuff like len(settings)
    def __len__(self) -> int:
        return len(self._settings)
    
    def __str__(self) -> str:
        out: str = "Settings data:"
        for name, data in self._settings.items():
            if data.get("sensititve", False):
                out = out+f"\n    {name}: <hidden>"
            elif isinstance(data["value"], str):
                out = out+f"\n    {name}: \"{data["value"]}\""
            else:
                out = out+f"\n    {name}: {str(data["value"])}"
        return out
    
    def __repr__(self) -> str:
        out: dict[str, SettingDict|HiddenObject] = {}
        for name, data in self._settings.items():
            if data.get("sensititve", False):
                out[name] = HiddenObject()
            else:
                out[name] = data
        return str(out)

# ----------------------------------------------------------------
# example usage
if __name__ == "__main__":

    # Some Example Settings
    example_settings = """
    {
        "foo": {
            "value": "bar",
            "description": "The first example setting"
        },
        "baz": {
            "value": 1,
            "sensititve": true
        }
    }
    """

    # Load the settings
    settings = Settings(io.StringIO(example_settings))

    # Print out the values
    print("-"*32)
    print("Before Change")
    print()
    print("Foo:", settings.get("foo"))
    print("Baz:", settings.get("baz"))
    print()

    # Set foo to qux
    settings.set("foo", "qux")

    # Print it out again
    print("-"*32)
    print("After Change")
    print()
    print("Foo:", settings.get("foo"))
    print("Baz:", settings.get("baz"))
    print()

    # Print the descriptions
    print("-"*32)
    print("Descriptions")
    print()
    print("Foo:", settings.getPropety("foo", "description"))
    print("Baz:", settings.getPropety("baz", "description"))
    print()

    # Some other functions
    print("-"*32)
    print("Extra data")
    print()
    print(f"There are {len(settings)} settings")
    print(f"The settings object is {repr(settings)}")
    print("Below is str(settings):")
    print(str(settings))