This example implements the [APF MP1000](https://en.wikipedia.org/wiki/APF-MP1000) games console and the 
[AFP Imagination Machine](https://en.wikipedia.org/wiki/APF_Imagination_Machine), which expands the games console into a 
home computer with a keyboard, a cassette drive,  and a Basic interpreter.

The cassette drive is mainly used for saving and loading Basic programs and is not supported.

There is a [Technical Manual](https://classictech.files.wordpress.com/2009/11/1980-apf-imagination-machine-technical-reference-manual-1-80.pdf) 
and a [disassembly of the system rom](https://orphanedgames.com/APF/apf_rom_and_cart_source/APF_ROM.asm).

The implementation uses the [nMigen 6800 CPU](https://github.com/RobertBaruch/n6800) by Robert Baruch.

It has an nMigen implementation of the Ulx3s OSD and SPI memory slave, which allows the ESP32 to upload cartridge games, 
to control the CPU, and to browse the RAM for debugging.

The machines uses the [Motorola MC6847](https://en.wikipedia.org/wiki/Motorola_6847) Video Display Generator, 
but the implementation used here is a cut-down version that supports only the modes required.

A PS/2 keyboard is used for the games controllers.

The machine was designed by the African American, Ed Smith - see https://www.youtube.com/watch?v=VcQWY9ZJiFo

