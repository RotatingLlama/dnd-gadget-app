TODO
====

GENERAL
-------
* Checks on both root menus to not cause problems if destroy() is called twice
* Long/Short rests and other rests:
  - Allow short rest stuff to get reset on long rest, too
  - Allow things with charges that never automatically reset
  - How to handle things that reset at 'dawn', or that don't regain all charges on reset (eg. Armour of Magical Strength)
* Add a way to spend hit dice outside of a short rest (eg. for Autognonmes with Mending)
* Rationalise dirname, name, title and subtitle
* After SD unplug/replug, character matrix dots are still present at character select screen
Emergency save can save to internal flash if sd unavailable.  Save out to sd when it comes back.
Have a system.json file
- Stores 'on-time', and any other non-character-specific data
  - Used to update RTC for somewhat-meaningful file access times
- Mandatory file part of directory recognition routine
- Gets saved at power-down
Way to skip character select screen and just go to last played
Oled menu to blank out default stuff before drawing
Add a menu item to view errors that have been caught and logged
spell slots can reset on short rest for some classes?
Have a "things" class, remove the items/spells distinction?
get rid of asserts, everywhere - replace with valueerror or something, at least
Proper error handling
Make render_sd_error() in gfx.py use blit_onto instead of load()
- Handle 2bpp onto 1bpp (to handle b&w with transparency)
- Define transparency colour in _blit_onto() - needed at least to construct p_bline
- Read spec for MONO_VLSB [https://docs.micropython.org/en/latest/library/framebuf.html#framebuf.framebuf.MONO_VLSB]
- Pixel arrangement for oled is *madness*.  Oled gfx assets are small, just img.load() them and use native fb.blit()
- Maybe instead, just have a 'scratch' framebuffer that's used for all off-screen manipulation, to avoid ad-hoc memory allocation


img
---
Fonts - review 1.26 capabilities
- https://github.com/micropython/micropython/releases/tag/v1.26.0#:~:text=which%20helps%20when%20implementing%20custom%20fonts
Support PNG???
- https://github.com/remixer-dec/mpy-img-decoder/tree/master
- Also https://github.com/Scondo/purepng

character.py
------------
On save, update individual lines rather than rewriting entire file.  To preserve formatting and comments
Way of communicating error in load()
implement die()
Move to JSON format?
Truncate charge item quantity at load-in, not at led matrix geometry calculation: max charges = 16 - n_spells

menu.py
-------
Option to scroll faster when adjusting a large number - still needed with irq improvement?


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
  - Unplugging the SD card resets the system (replug will reload the char select menu)
* Significantly improved rotary dial responsiveness (hw.py switched to hard interrupts)
* Improved Play Screen layout and added background image support (background.2ink)
* Added brightness control for matrix
* Added battery monitor
 - Needle now wobbles when battery is low and not charging.
 - New low-battery graphic will display in place of character head.
* Added natty loading and poweroff animations
* At poweroff:
  - Eink progress is now indicated by moving needle.
  - Oled powers off properly, instead of remaining on after program halt.

Invisible Changes
-----------------
* Renamed UI to HAL
  - ui.py is now hal.py
  - UI() is now HAL()
  - Classes now have a ref to hal instead of to ui
* hal.py:
  - Added more granular way of locking hardware features using ClientRegistrations (CRs) with hal.register() and unregister()
  - Added hal.needle object and wobble() method
* Reworked main_sequence() as phase control, like wm project
* hw.py
  - Replaced running average battery monitor used by voltage_stable() with hysteresis to better eliminate noise
  - Made _isr_rot() be Viper
* character.py
  - Added short timeout before save, to allow multiple changes to aggregrate together
  - Removed show_all_hp()
* menu.py
  - Menus now rely on new CR feature from hal.py, replacing previous parent/child system
  - Combined both matrix menus into one unified menu
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
