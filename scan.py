#!/usr/bin/env python3
"""pydigitize.

Usage:
    scan.py [options] [OUTPUT]

Examples:
    scan.py out/
    scan.py out/document.pdf
    scan.py out/ -n document -k foo,bar

Args:
    OUTPUT         This can either be a filename or a directory name.

Options:
    -h --help      Show this help.
    --version      Show version.

    -p PROFILE     The profile to use.

    -n NAME        Text that will be incorporated into the filename.
    -t DATE        Use the specified date string (format: YYYYMMDD)
    -k KEYWORDS    Comma separated keywords that will be added to the PDF metadata.

    -d DEVICE      Set the device [default: brother4:net1;dev0].
    -r RESOLUTION  Set the resolution [default: 300].
    -c PAGES       Page count to scan [default: all pages from ADF]

    --skip-ocr     Don't run OCR / straightening / cleanup step.

    --verbose      Verbose output
    --debug        Debug output

"""
import datetime
import glob
import logging
import os.path
import re
import sys
import tempfile

import docopt
from sh import cd, mkdir, mv
from slugify import slugify
import toml

try:
    from sh import scanimage
except ImportError:
    print('Error: scanimage command not found. Please install sane.')
    sys.exit(1)

try:
    from sh import tiffcp, tiff2pdf
except ImportError:
    print('Error: tiffcp / tiff2pdf commands not found. Please install libtiff.')
    sys.exit(1)

try:
    from sh import ocrmypdf
except ImportError:
    print('Error: ocrmypdf command not found. Please install ocrmypdf.')
    sys.exit(1)

try:
    from sh import tesseract  # noqa
except ImportError:
    print('Error: tesseract command not found. Please install tesseract.')
    sys.exit(1)

try:
    from sh import unpaper  # noqa
except ImportError:
    print('Error: unpaper command not found. Please install unpaper.')
    sys.exit(1)


logger = logging.getLogger('pydigitize')


VALID_RESOLUTIONS = (100, 200, 300, 400, 600)
START_TIME = datetime.datetime.now()


def prefix():
    duration = (datetime.datetime.now() - START_TIME).total_seconds()
    return '\033[92m\033[1m+\033[0m [{0:>5.2f}s] '.format(duration)


class Scan:

    def __init__(self, *, resolution, device, output, name=None, datestring=None, keywords=None):
        """
        Initialize scan class.

        Added attributes:

        - resolution
        - device
        - output_path
        - keywords

        """
        # Validate and store resolution
        def _invalid_res():
            print('Invalid resolution. Please use one of {!r}.'.format(VALID_RESOLUTIONS))
            sys.exit(1)
        try:
            if int(resolution) not in VALID_RESOLUTIONS:
                _invalid_res()
        except ValueError:
            _invalid_res()
        else:
            self.resolution = resolution

        # Store device
        self.device = device

        # Store keywords
        self.keywords = set() if keywords is None else set(keywords)

        # Validate and set timestamp
        if datestring is None:
            timestamp = START_TIME.strftime('%Y%m%d-%H%M%S')
        else:
            datestring = re.sub(r'[^0-9]', '', datestring)
            timestamp = datestring or START_TIME.strftime('%Y%m%d-%H%M%S')

        # Validate and store output path
        if os.path.isdir(output):
            if name is None:
                filename = '{}.pdf'.format(timestamp)
            else:
                filename = '{}-{}.pdf'.format(timestamp, slugify(name, to_lower=True))
            output_path = os.path.join(output, filename)
        elif os.path.dirname(output) == '' or os.path.isdir(os.path.dirname(output)):
            output_path = output
        else:
            print('Output directory must already exist.')
            sys.exit(1)
        self.output_path = os.path.abspath(output_path)
        logger.debug('Output path: %s', self.output_path)

    def prepare_directories(self):
        """
        Prepare the temporary output directories.

        Added attributes:

        - workdir

        """
        print(prefix() + 'Creating temporary directory...')
        self.workdir = tempfile.mkdtemp(prefix='pydigitize-')

    def scan_pages(self):
        """
        Scan pages using ``scanimage``.
        """
        print(prefix() + 'Scanning...')
        scanimage_args = {
            'x': 210, 'y': 297,
            'device_name': self.device,
            'batch': True,
            'format': 'tiff',
            'resolution': self.resolution,
            '_ok_code': [0, 7],
        }
        logger.debug('Scanimage args: %r' % scanimage_args)
        scanimage(**scanimage_args)

    def combine_tiffs(self):
        """
        Combine tiffs into single multi-page tiff.
        """
        print(prefix() + 'Combining image files...')
        files = sorted(glob.glob('out*.tif'))
        logger.debug('Joining %r', files)
        tiffcp(files, 'output.tif', c='lzw')

    def convert_tiff_to_pdf(self):
        """
        Convert tiff to pdf.

        TODO: use convert instead?

        """
        print(prefix() + 'Converting to PDF...')
        tiff2pdf('output.tif', p='A4', o='output.pdf')

    def do_ocr(self):
        """
        Do character recognition (OCR) with ``ocrmypdf``.
        """
        print(prefix() + 'Running OCR...')
        args = ['-l', 'deu', '-d', '-c']
        if self.keywords:
            args.extend(['--keywords', ','.join(self.keywords)])
        args.extend(['output.pdf', 'clean.pdf'])
        ocrmypdf(*args)

    def process(self, *, skip_ocr=False):
        # Prepare directories
        self.prepare_directories()
        cd(self.workdir)

        # Scan pages
        self.scan_pages()

        # Combine tiffs into single multi-page tiff
        self.combine_tiffs()

        # Convert tiff to pdf
        self.convert_tiff_to_pdf()

        # Do OCR
        if skip_ocr is False:
            self.do_ocr()
            filename = 'clean.pdf'
        else:
            filename = 'output.pdf'

        # Move file
        print(prefix() + 'Moving resulting file...')
        cd('..')
        mv('{}/{}'.format(self.workdir, filename), self.output_path)

        print('\nDone: %s' % self.output_path)


if __name__ == '__main__':
    args = docopt.docopt(__doc__, version='pydigitize 0.1')
    if args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    logger.debug('Command line args: %r' % args)

    default_output = tempfile.mkdtemp(prefix='pydigitize-', suffix='-out')

    # Default args
    kwargs = {
        'output': default_output,
        'keywords': {'pydigitize'},
    }
    skip_ocr = False

    # Process profile
    if args['-p'] is not None:
        # Load profiles
        with open('profiles.toml', 'r') as conffile:
            profiles = toml.loads(conffile.read())

        # Create list of all profiles
        all_profiles = []

        def _parse_profile(k, v, prefix=None):
            if isinstance(v, dict):
                if prefix is None:
                    new_prefix = k
                else:
                    new_prefix = '%s.%s' % (prefix, k)
                all_profiles.append(new_prefix)
                for kk, vv in v.items():
                    _parse_profile(kk, vv, new_prefix)

        for k, v in profiles.items():
            _parse_profile(k, v)

        # Find profile
        profile = profiles
        profile_name = args['-p']
        profile_parts = profile_name.split('.')
        for part in profile_parts:
            found = profile.get(part)
            if found is None:
                print('Profile not found: {}'.format(profile_name))
                print('\nAvailable profiles:')
                for name in sorted(all_profiles):
                    print(' - %s' % name)
                sys.exit(1)
            profile = found

        # Update args
        if 'path' in profile:
            kwargs['output'] = profile['path']
        if 'name' in profile:
            kwargs['name'] = profile['name']
        if 'ocr' in profile:
            skip_ocr = not bool(profile['ocr'])
        if 'keywords' in profile:
            kwargs['keywords'].update(profile['keywords'])

    # Argument overrides
    kwargs['resolution'] = args['-r']
    kwargs['device'] = args['-d']
    if args['OUTPUT']:
        kwargs['output'] = args['OUTPUT']
    if args['--skip-ocr'] is True:
        skip_ocr = True
    if args['-n']:
        kwargs['name'] = args['-n']
    if args['-t']:
        kwargs['datestring'] = args['-t']
    if args['-k']:
        keywords = [k.strip() for k in args.get('-k', '').split(',')]
        kwargs['keywords'].update(keywords)

    print('                           ____')
    print('  ________________________/ O  \___/')
    print(' <_/_\_/_\_/_\_/_\_/_\_/_______/   \\\n')

    scan = Scan(**kwargs)
    scan.process(skip_ocr=skip_ocr)
