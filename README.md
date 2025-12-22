D&D Gadget
==========

Motivation
----------
A necessary feature of many tabletop roleplaying games (TTRPGs) is the requirement to keep track of a large number of character statistics.  Health points, gold, spell slots, uses remaining of that magic sword you picked up - the list goes on.  Of course various apps exist to help keep track of all this, but all of them are either awkward, unintuitive, unpleasant, or involve supporting corporations with questionable ethics.  Or some combination of the above.

This is where the D&D Gadget comes in.  It doesn't replace a character sheet, it won't tell you the text of your class features and it certainly won't take from you the enjoyment of rolling your clacky math rocks.  What is _does_ aim for however, is to remove the need to ever cross through, rub out or rewrite anything, ever again.  Any quantity that varies through play is captured in this convenient and eye-catching open-source device, for quick reference and easy revision.

This repository is for the firmware that runs on the device (the "app").  The hardware aspects (PCB and enclosure) are not yet ready for publishing.

How to Use
----------
TODO: Complete this section.  Photos, etc.

Below: How to set up.

File Structure
--------------

The app expects the following directory structure on the SD card:
```
/TTRPG/Characters                       [mandatory file path, must exist]
                 /char1                 [named freely]
                       /stats.json      [mandatory, must exist]
                       /head.pi         [optional]
                       /background.pi   [optional]
                 /char2
                       /stats.json
                       /head.pi
                 /char3
                       etc.
```
- `stats.json` is the character's savefile - see below for details.
- `head.pi` is a 64x64 character head image, in the `.pi` format
- `background.pi` is a 360x240 `.pi` image to serve as the playscreen background.

Images
------
The app uses a custom, low-complexity bitmap format called `.pi` for all of its images.  The format is designed to be simple for microcontrollers to work with, and specifically easy for MicroPython to load into memory and use directly with its builtin [`framebuf`](https://docs.micropython.org/en/latest/library/framebuf.html) class.  You can convert between `.pi` and most common image formats using the `imgconvert` scripts in the `Supporting Code` directory.

The e-ink display supports three colours: white, black and red.  The `.pi` format also supports a 1-bit alpha channel, with transparent areas represented as a fourth colour.  When preparing images for conversion to `.pi`, use the following colour pallet:
- White: `#ffffff`
- Black: `#000000`
- Red: `#ff0000` (Note: This will appear as approximately `#9f2831` on the e-ink display, but the conversion script assumes pure red.)
- Transparent: `#ff00ff`

For details of the `.pi` format, refer to `libpi.py` (either version).

Savefiles
---------
All of a character's information is stored in their `stats.json` file.
- The file uses standard JSON format.
- Supported fields are shown in the example below.
- Spell slots are stored in order, starting from level 1.
- `charges` are anything that has a given number of uses per time interval.  For example, a Druid may have 3 uses of Wildshape per short rest.  For each 'charge,' specify:
  - Its name
  - How many charges/uses it currently has remaining
  - How many it has when it resets
  - What triggers a reset:
    - Allowed codes are "lr", "sr" and "dawn", for things that reset at long rests, short rests and dawn respectively.
    - It's valid to specify any number of these intervals, including none.
```
{
      "name": "Hemlock",
      "title": "L5 Wizard",
      "xp": 9256,
      "copper": 0,
      "silver": 0,
      "gold": 11,
      "electrum": 0,
      "hitdice": {
            "current": 3,
            "max": 5
      },
      "hp": {
            "current": 29,
            "max": 32,
            "temporary": 10
      },
      "spells": [
            {"current": 4, "max": 4},
            {"current": 1, "max": 3},
            {"current": 0, "max": 2}
      ],
      "charges": [
            {"current": 1, "max": 1, "name": "Arcane Recovery", "reset": ["lr"]},
            {"current": 3, "max": 3, "name": "Fey Step", "reset": ["lr"]},
            {"current": 0, "max": 1, "name": "Cape of the Mountbank", "reset": ["lr","dawn"]},
            {"current": 1, "max": 1, "name": "Dagger of Venom", "reset": ["lr","dawn"]},
            {"current": 1, "max": 3, "name": "Rusty Bag of Tricks", "reset": ["lr","dawn"]}
      ]
}
```

Installation
------------
The app is designed to work with MicroPython 1.26.  Setup requires some basic familiarity with the use of MicroPython and the Raspberry Pi Pico:
- Load the MicroPython firmware onto the board in the normal way.
- Copy the contents of the `/App` directory into the MicroPython filesystem.
- Create an SD card to the above specification and insert it.
- To start the app:
  - If the device is connected to a PC:  Run `main.py` from an IDE (such as Thonny) while holding down the 'back' button.
  - If the device is _not_ connected to a PC, just press the power button.
