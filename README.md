D&D Gadget
==========

Expects the following directory structure on the SD card:
```
/TTRPG/Characters                       [mandatory file path]
                 /char1                 [named freely]
                       /stats.txt       [mandatory]
                       /head.2ink       [optional]
                       /background.2ink [optional]
```
- `head.2ink` is a 64x64 character head image, in the 2ink format
- `background.2ink` is a 360x240 2ink image to serve as the playscreen background.
- `stats.txt` example:
```
# BASIC INFO
#
name=Hemlock
title=Hemlock
subtitle=L5 Wizard
level=5
xp=9256

# CURRENCY
#
gold=11
silver=0
copper=0
electrum=0

# HIT POINTS
#
hp_current=21
hp_max=32
hp_temp=0

# HIT DICE
#
hd_current=5
hd_max=5

# SPELLS
#
spell_curr:0=0
spell_max:0=4
#
spell_curr:1=0
spell_max:1=3
#
spell_curr:2=0
spell_max:2=2
#

# ITEMS/THINGS WITH CHARGES
#
charge_name:0=Arcane Recovery
charge_curr:0=1
charge_max:0=1
charge_reset:0=lr
#
charge_name:1=Fey Step
charge_curr:1=3
charge_max:1=3
charge_reset:1=lr
#
charge_name:2=Cape of the Mountbank
charge_curr:2=0
charge_max:2=1
charge_reset:2=lr
#
charge_name:3=Dagger of Venom
charge_curr:3=1
charge_max:3=1
charge_reset:3=lr
#
charge_name:4=Rusty Bag of Tricks
charge_curr:4=1
charge_max:4=3
charge_reset:4=lr
#
```