#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan.py.

Usage:
    scan.py [-r RESOLUTION] [-d DEVICE] [-p PAGES] (img|doc)

Options:
    -h --help      Show this help.
    --version      Show version.
    -r RESOLUTION  Set the resolution [default: 300].
    -d DEVICE      Set the device [default: brother4:net1;dev0].
    -p PAGES       Number of pages to scan [default: all pages from ADF]

"""
from __future__ import print_function, division, absolute_import, unicode_literals

import sys
import datetime

import docopt
from sh import cd, mkdir, scanimage, tiffcp, tiff2pdf, glob, mv
import sh; ocrmypdf = getattr(sh, 'OCRmyPDF.sh')


VALID_RESOLUTIONS = (100, 200, 300, 400, 600)
OUTPUT_BASE = '/home/danilo/brscan/%s' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S')


def scan(resolution, device):

    # Validate args
    def _invalid_res():
        print('Invalid resolution. Please use one of {!r}.'.format(VALID_RESOLUTIONS))
        sys.exit(1)
    try:
        if int(resolution) not in VALID_RESOLUTIONS:
            _invalid_res()
    except ValueError:
        _invalid_res()

    # Prepare directories
    print('Creating directory...')
    mkdir(OUTPUT_BASE, parents=True)
    cd(OUTPUT_BASE)

    # Scan pages
    print('Scanning...')
    scanimage_args = {
        'x': 210, 'y': 297,
        'device_name': device,
        'batch': True,
        'format': 'tiff',
        'resolution': resolution,
        '_ok_code': [0, 7],
    }
    scanimage(**scanimage_args)

    # Combine tiffs into single multi-page tiff
    print('Combining image files...')
    tiffcp(glob('out*.tif'), 'output.tif', c='lzw')

    # Convert tiff to pdf
    print('Converting to PDF...')
    tiff2pdf('output.tif', p='A4', o='output.pdf')
    # TODO: use convert instead?

    # Do OCR
    print('Running OCR...')
    ocrmypdf('-l', 'deu', '-o', resolution, '-d', '-c', 'output.pdf', 'clean.pdf')

    # Move file
    print('Moving resulting file...')
    cd('..')
    mv('{0}/clean.pdf {0}.pdf'.format(OUTPUT_BASE))

    print('Done: %s.pdf' % OUTPUT_BASE)

if __name__ == '__main__':
    args = docopt.docopt(__doc__, version='scan.py 0.1')
    print(args)
    scan(resolution=args['-r'], device=args['-d'])
