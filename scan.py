#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pydigitize.

Usage:
    scan.py [options]

Options:
    -h --help      Show this help.
    --version      Show version.

    -d DEVICE      Set the device [default: brother4:net1;dev0].
    -r RESOLUTION  Set the resolution [default: 300].

    -p PAGES       Number of pages to scan [default: all pages from ADF]
    -o OUTPUT      Output file or directory

    --verbose      Verbose output
    --debug        Debug output

"""
from __future__ import print_function, division, absolute_import, unicode_literals

import sys
import glob
import datetime
import os.path
import logging

import docopt
from sh import cd, mkdir, scanimage, tiffcp, tiff2pdf, mv
import sh; ocrmypdf = getattr(sh, 'OCRmyPDF.sh')


logger = logging.getLogger('pydigitize')


VALID_RESOLUTIONS = (100, 200, 300, 400, 600)
OUTPUT_BASE = '/home/danilo/brscan'
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')


def scan(resolution, device, output):

    # Validate args
    def _invalid_res():
        print('Invalid resolution. Please use one of {!r}.'.format(VALID_RESOLUTIONS))
        sys.exit(1)
    try:
        if int(resolution) not in VALID_RESOLUTIONS:
            _invalid_res()
    except ValueError:
        _invalid_res()
    if os.path.isdir(output):
        output_path = os.path.join(output, TIMESTAMP + '.pdf')
    elif os.path.isdir(os.path.dirname(output)):
        output_path = output
    else:
        print('Output directory must already exist.')
        sys.exit(1)

    # Prepare directories
    print('Creating directory...')
    workdir = os.path.join(OUTPUT_BASE, TIMESTAMP)
    mkdir(workdir, parents=True)
    cd(workdir)

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
    logger.debug('Scanimage args: %r' % scanimage_args)
    scanimage(**scanimage_args)

    # Combine tiffs into single multi-page tiff
    print('Combining image files...')
    files = sorted(glob.glob('out*.tif'))
    logger.debug('Joining %r', files)
    tiffcp(files, 'output.tif', c='lzw')

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
    mv('%s/clean.pdf' % workdir, output_path)

    print('Done: %s' % output_path)

if __name__ == '__main__':
    args = docopt.docopt(__doc__, version='pydigitize 0.1')
    if args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    logger.debug('Command line args: %r' % args)
    default_output = os.path.join(OUTPUT_BASE, TIMESTAMP)
    scan(resolution=args['-r'], device=args['-d'], output=args['-o'] or default_output)
