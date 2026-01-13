#!/usr/bin/env bash

mv -f demo.gif demo.orig.gif
gifsicle -O=3 --colors 32 --color-method blend-diversity demo.orig.gif -o demo.gif
rm -f demo.orig.gif
