import abc
import asyncio
import json
import os
import shutil
import threading
import time

from typing import Optional, Any

# ----------------------------------------------------------------
# The Base Class

class StorageBase(abc.ABC):
    """The Base for a storage container"""

    def __init__(self, filename: str, default: Optional[str] = None, autosave_interval: float = 60) -> None:
        """loads the storage

        Args:
            filename: the name of the storage file
            default: the name of the fallback file
            autosave_interval: how often (in seconds) the file should automatically be saved
        
        Raises:
            FileNotFoundError: The specified file was not found.
            json.JSONDecodeError: The file does not contain valid json.
        """
        self.filename: str = filename
        self.autosave_interval: float = autosave_interval

        self._storage: dict[str, Any]
        self._next_save: float = time.time()+autosave_interval

        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                self._storage = json.load(f)
        elif default:
            with open(default, "r") as f:
                self._storage = json.load(f)
        else:
                raise FileNotFoundError("The storage file was not found")
        
        self._start_autosave_loop()
    
    # ----------------------------------------------------------------
    # general internal functions
    @abc.abstractmethod
    def _start_autosave_loop(self) -> None:
        """Starts the autosave loop"""

    # ----------------------------------------------------------------
    # general operations
    def get(self, name: str, default: Any = None) -> Any:
        """returns the stored value
        
        Args:
            name: The name of the object
            default: the value to use if the object does not exisit
        Returns:
            data: The value of the object
        """
        return self._storage.get(name, default)
    
    def set(self, name: str, value: Any) -> None:
        """sets an object to the given value
        
        Args:
            name: the name of the object
            value: what the object should be set to
        """
        self._storage[name] = value
    
    def save(self, filename: Optional[str] = None) -> None:
        """Saves the storage to file
        
        Args:
            filename: the name of the storage-file. Defaults to the one used for loading the storage
        Raises:
            TypeError: there is an unserializeable object in the storage
        """
        # we will write the data to a temporaty file first
        # and then move the file as this ensures that the
        # data cannot be lost when there is an error while
        # writing the file

        # write to a temporary file
        final_filename = filename or self.filename

        directory, name = os.path.split(final_filename)
        tmp_path = os.path.join(directory, f"tmp_{name}")

        with open(tmp_path, "w+") as f:
            json.dump(self._storage, f)

        # replace the old file
        shutil.copyfile(tmp_path, final_filename)
    
    @abc.abstractmethod
    def stop(self) -> None:
        """Stops autosaving"""
    
    # ----------------------------------------------------------------
    # python internals to allow for stuff like len(settings)
    def __len__(self) -> int:
        return len(self._storage)
    
    def __str__(self) -> str:
        out: str = "Storage:"
        for name, data in self._storage.items():
            if isinstance(data["value"], str):
                out = out+f"\n    {name}: \"{data["value"]}\""
            else:
                out = out+f"\n    {name}: {str(data["value"])}"
        return out
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(filename=\"{self.filename}\", autosave_interval={self.autosave_interval}, data={repr(self._storage)})"


# ----------------------------------------------------------------
# Main Classes

class AsyncStorage(StorageBase):
    """The async variant of the storage container
    
    Requires an asyncio EventLoop to be running.
    """

    def _start_autosave_loop(self) -> None:
        event_loop = asyncio.get_event_loop()
        self._task = event_loop.create_task(self._autosave())
    
    def stop(self) -> None:
        self._task.cancel()
    
    async def _autosave(self):
        while True:
            await asyncio.sleep(self._next_save - time.time())
            self.save()
            self._next_save = time.time() + self.autosave_interval

class ThreadingStorage(StorageBase):
    """The threading variant of the storage container"""

    def __init__(self, filename: str, default: Optional[str] = None, autosave_interval: float = 60) -> None:
        self._lock = threading.Lock()
        super().__init__(filename, default, autosave_interval)

    def _start_autosave_loop(self) -> None:
        self._running = True
        threading.Thread(target=self._autosave, daemon=True).start()
    
    def stop(self) -> None:
        self._running = False

    def _autosave(self):
        time.sleep(self._next_save - time.time())
        while self._running:
            self.save()
            self._next_save = time.time() + self.autosave_interval
            time.sleep(self._next_save - time.time())

    # When dealing with threads we should lock those methods
    def get(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return super().get(name, default)
    
    def set(self, name: str, value: Any) -> None:
        with self._lock:
            return super().set(name, value)
    
    def save(self, filename: Optional[str] = None) -> None:
        with self._lock:
            return super().save(filename)