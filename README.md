# pydigitize

Requirements:

- Python 3.x
- OCRmyPDF 3.x
- libtiff 4.x
- sane 1.x
- unpaper

## Usage

See `./scan.py --help`.

## Profiles

If you want to use profiles, create a `profiles.toml` file in the current
directory.

For every profile you can specify the following parameters:

- `path`: The output directory
- `name`: Set a string that will be included in every filename in slugified form
- `ocr`: Whether to run OCR, straightening and cleanup on the scanned document

You can also create sub-profiles. They inherit the settings from the parent.

Example:

```toml
[bill]
path = "/home/user/bills/"
name = "bill"
ocr = true

[bill.dentist]
name = "dentist"

[drawing]
path = "/home/user/drawings/"
ocr = false
```

Then pass the name of the profile to the `scan.py` command using the `-p`
parameter.

    ./scan.py -p bill.dentist

You can of course override your parameters:

    ./scan.py -p bill -n amazon
