TODO
====

GENERAL
-------
* Proper SD card handling
  - On unplug, put warning on oled, and:
    - In char select: prevent any selection
    - In play screen: allow normal play, but defer saves until replug
  - On replug, init card and reverse the above contingencies
* Long/Short rests and other rests:
  - Allow short rest stuff to get reset on long rest, too
  - Allow things with charges that never automatically reset
  - How to handle things that reset at 'dawn', or that don't regain all charges on reset (eg. Armour of Magical Strength)
* Move titles on play screen down slightly (too close to bottom of arc)
Way to skip character select screen and just go to last played
Oled menu to blank out default stuff before drawing
spell slots can reset on short rest for some classes?
Have a "things" class, remove the items/spells distinction?
get rid of asserts, everywhere - replace with valueerror or something, at least
Proper error handling
Rotary still misses steps, particularly if it's spun quickly - needs checking with scope

img
---
Fonts

character.py
------------
On save, update individual lines rather than rewriting entire file.  To preserve formatting and comments
Way of communicating error in load()
implement die()

menu.py
-------
OLED tells you what you're selecting on the matrix, plus curr/max
Option to scroll faster when adjusting a large number

gadget.py
---------
Reduce need for menu objects to know about char, etc.



Gadget v0.3
===========

Gameplay Changes & Bugfixes
----------------
* Hit dice:
  - Now reset correctly on long rest
  - Are now spendable on short rest, but can't be incremented except by long rest
* Fixed needle going to wrong place after long rest with temp hp
* Fixed needle moving wrong way on damage

Visible Changes
---------------
* Moved all character data to external SD card
* Improved Play Screen layout and added background image support (background.2ink)
* Added brightness control for matrix
* Added battery monitor
 - Needle now wobbles when battery is low and not charging.
 - New low-battery graphic will display in place of character head.

Invisible Changes
-----------------
* Renamed UI to HAL
  - ui.py is now hal.py
  - UI() is now HAL()
  - Classes now have a ref to hal instead of to ui
* hal.py:
  - Added more granular way of locking hardware features with hal.register() and unregister()
  - Added hal.needle object and wobble() method
* Reworked main_sequence() as phase control, like wm project
* hw.py
  - Replaced running average battery monitor used by voltage_stable() with hysteresis to better eliminate noise
  - Made _isr_rot() be Viper
* character.py
  - Added short timeout before save, to allow multiple changes to aggregrate together
  - Removed show_all_hp()
* menu.py
  - Added 'prompt' option to SimpleAdjuster, so prompt can be different from name in menu
  - Added absolute adjuster callback to SimpleAdjuster, to complement existing relative one
* common.py
  - Moved menu.py's timeout_watcher into the new DeferredTask class, for wider use

Gadget v0.2 - 11 Jul 2025
=========================
* Added Character Select screen
* Simplified matrix menus:
  - No more adjusters, btn/back now adjust directly.
  - Added interaction timeout.
* Added Hit Dice and Electrum tracking
* Battey management
  - Added running average for battery level to prevent fluctuating readings
  - Added batt_pc() in hw.py to give percentage charge
  - Removed battery logger (stop creating battery.log file)
* Made damage menu go backwards - damage is now negative rather than positive
* Temporary HP adjuster now always starts at zero rather than current level
* Needle now returns to zero at power down

Gadget v0.1 - 04 June 2025
==========================
* First version; bare minimum functionality
