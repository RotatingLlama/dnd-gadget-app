from machine import UART, Pin
from os import dupterm

# What happens after soft reset?
# "A serial UART REPL will restore its default hardware configuration (baud rate, etc)."
# https://docs.micropython.org/en/latest/reference/reset_boot.html#soft-reset
#
# This file should get re-run after a soft reset:
# https://forum.micropython.org/viewtopic.php?t=897#:~:text=Re:%20Reset%20Question&text=A%20soft%20reset%20does%20cause,back%20to%20its%20reset%20state.


# Set up the UART
uart = UART(0)
# 9600 baud is default?
# mpremote etc won't work unless 115200
# https://github.com/orgs/micropython/discussions/17416#discussioncomment-13348703
uart.init( baudrate=115200, bits=8, parity=None, stop=1, tx=Pin(0), rx=Pin(1) )

# Send the REPL to the UART
dupterm(uart)
print(f'dupterm:\n{uart}')
