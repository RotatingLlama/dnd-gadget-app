import vfs
from gadget_hw import HW
hw=HW()
hw.sd.try_init_card()
vfs.mount(hw.sd.card, '/sd')