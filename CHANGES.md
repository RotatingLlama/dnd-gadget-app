TODO
====
* Saving
  * If no SD card on bootup, check internal memory to see if we have anything saved there
* Hierarchical menus
  - Add a menu item to view errors that have been caught and logged
  - Add a menu item to take a screenshot
* How to handle things that reset at 'dawn', or that don't regain all charges on reset (eg. Armour of Magical Strength)
  - This will need another menu entry.  Wait to implement after heirarchical menus are added.
* Combine 'charges' and other counters (gold, xp etc.)
  - 'reset' property is optional
  - 'max' property is optional
  - Assume zero minimum
  - Can appear on matrix if 'max' is present, and 6 or less
  - Eligible items appear on matrix on first-come-first-served basis.  Overflow goes into:
  - New 'character' menu on oled, after Damage/Heal
    - Contains overflow from matrix and anything ineligible for matrix
    - Order of appearance is order in savefile
  - Rationalise character load-in and matrix geometry calculation:
    - Both of these have opinions about how many charges are permissible
    - These opinions should always match, or better yet come from the same source
* Fonts
  - https://github.com/peterhinch/micropython-font-to-py
  - https://github.com/easytarget/microPyEZfonts
  - Honorable mention https://github.com/nickpmulder/ssd1306big/blob/main/ssd1306big.py
- Improve the way the matrix animations work.  Viperise?
- Way to skip character select screen and just go to last played
- spell slots can reset on short rest for some classes
- menu.py fast scrolling should trigger on more predictable intervals
  - eg. 40, 400, 4000 etc.
  - Instead of after n rotations, leading to 40, 440, 4440, etc.
  - Move some logic out of SimpleAdjuster and DoubleAdjuster, have the IncrementAccelerator know the entire adjustment value (instead of just one rotation at a time)
  - Just verify/clamp the total adjustment that IncrementAccelerator presents
  - Feedback to IncrementAccelerator if it's being clamped?
  - Would help to give IA a min/mac d tuple:
    - Tuple would need to be dynamically generated (eg. max hp varies with temp hp)
    - But tuple can be requested as soon as IA goes out of 'reset' state
    - Safe to assume it won't change during the adjustment (just maybe as a consequence of it)
- OLED menu and idle screen can draw simultaneously on rare occasions.  Fix this
  - Both SimpleAdjuster.render_title() and _oled_idle_render() call oled.fill(0) before doing anything, so this shouldn't happen
  - Neither of the above functions are coroutines or yield during execution
  - Unclear how/why this happened.  Get a photo next time.
- Have a system.json file
  - Determines which character directories to use
  - Perhaps better RTC tracking than current ad-hoc savefiles method
  - Mandatory file part of directory recognition routine
  - Gets saved at power-down
- get rid of asserts, everywhere - replace with valueerror or something, at least
- Proper error handling
- Make render_sd_error() in gfx.py use blit_onto instead of load()
  - Handle 2bpp onto 1bpp (to handle b&w with transparency)
  - Define transparency colour in _blit_onto() - needed at least to construct p_bline
  - Read spec for MONO_VLSB [https://docs.micropython.org/en/latest/library/framebuf.html#framebuf.framebuf.MONO_VLSB]
  - Pixel arrangement for oled is *madness*.  Oled gfx assets are small, just img.load() them and use native fb.blit()
  - Maybe instead, just have a 'scratch' framebuffer that's used for all off-screen manipulation, to avoid ad-hoc memory allocation
- Implement die()
- Support PNG???
  - https://github.com/remixer-dec/mpy-img-decoder/tree/master
  - Also https://github.com/Scondo/purepng


Gadget v0.4 - WIP
=================

Gameplay Changes & Bugfixes
---------------------------
* Nothing yet

Visible Changes
---------------
* Changed savefiles from custom format to JSON
  - Removed 'level' from savefile as it wasn't being used for anything
* If SD is removed during gameplay, saves will seamlessly switch to internal storage instead
  - Next time a validly-formatted SD card appears, the internal save will get moved to it automatically
  - If a character file already exists on the SD with the same name, the file being moved will be automatically renamed to prevent overwriting.
  - Both versions of the character will now be available for selection
* When entering large numbers through the dial, increments now accelerate dynamically to speed up the process
* Added bootup logo on oled, to hide spurious SD card errors that get shown while system is booting

Invisible Changes
-----------------
* Now sets internal clock at startup based on most recent savefile time


Gadget v0.3 - 01 Nov 2025
=========================

Gameplay Changes & Bugfixes
---------------------------
* Hit dice:
  - Now reset correctly on long rest
  - Are now spendable on short rest, as well as being individually settable
* Fixed needle going to wrong place after long rest with temp hp
* Fixed needle moving wrong way on damage

Visible Changes
---------------
* Moved all character data to external SD card
  - Unplugging the SD card resets the system (replug will reload the char select menu)
  - Character 'name' and 'title' are now used, instead of 'title' and 'subtitle'
* Significantly improved rotary dial responsiveness (hw.py switched to hard interrupts)
* Improved Play Screen layout and added background image support (background.2ink)
* Added brightness control for matrix
* Charges can now be reset by long rest AND short rest.  Separate with a comma in stats.txt, eg. charge_reset:2=lr,sr
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
* Characters are now verified before showing up on char select screen.  Everything on that screen has now already been loaded correctly.
* hw.py
  - Replaced running average battery monitor used by voltage_stable() with hysteresis to better eliminate noise
  - Made _isr_rot() be Viper
* character.py
  - Added timeout before save, to allow multiple changes to aggregrate together
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
