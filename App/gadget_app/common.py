# Misc common data and code
#
# T. Lloyd
# 29 Oct 2025

from micropython import const
import asyncio
import time

# HAL priority levels
HAL_PRIORITY_IDLE = const(1)
HAL_PRIORITY_MENU = const(10)
HAL_PRIORITY_SHUTDOWN = const(100)

# SD directory structure
SD_ROOT = const('/sd')
SD_DIR = const('TTRPG')
#
CHAR_SUBDIR = const('Characters')
CHAR_STATS = const('stats.txt')
CHAR_HEAD = const('head.pi')
CHAR_BG = const('background.pi')

# As soon as this class is touch()'d, it will begin counting down to execute callback()
# If it's touch()ed again during the countdown, the countdown resets
# Countdown can be cancelled with untouch()
# Requires timeout, number of milliseconds to count down before executing
# callback, a callable that will get run and is not passed any args.
class DeferredTask:
  def __init__(self, timeout:int, callback, poll:int=200):
    self.timeout = timeout
    self.callback = callback
    self._last_touch = None
    self._timeout_task = asyncio.create_task( self._timeout_watcher(poll) )
  
  # Run as a polling loop because Task.cancel() doesn't work (as of MP 1.24.1)
  async def _timeout_watcher(self, poll:int ):
    sms = asyncio.sleep_ms
    tms = time.ticks_ms
    ttd = time.ticks_diff
    while True:
      await sms( poll )
      
      # Don't do anything if we don't have an active timeout
      if self._last_touch is None:
        continue
      
      # If the time is up
      if ttd( tms(), self._last_touch ) >= self.timeout:
        
        # Trigger the callback
        self.callback()
        
        # Reset
        self._last_touch = None
  
  # Are we counting down right now?
  def is_dirty(self):
    return self._last_touch is not None
  
  # Set/update the timeout
  def touch(self):
    self._last_touch = time.ticks_ms()
  
  # Cancel any timeout
  def untouch(self):
    self._last_touch = None
  