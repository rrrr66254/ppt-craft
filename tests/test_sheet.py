from PIL import Image

from sheet import make_sheet


def test_sheet_grid_size(tmp_path):
    paths = []
    for i in range(5):
        p = tmp_path / f"slide-{i + 1:02d}.png"
        Image.new("RGB", (960, 540), (i * 40, 100, 100)).save(p)
        paths.append(p)
    out = make_sheet([paths[:4], paths[4:]], tmp_path / "sheet.png", numbered=True)
    im = Image.open(out)
    assert im.width == 16 + 4 * (480 + 16)
    assert im.height == 16 + 2 * (270 + 16)


def test_sheet_with_labels_adds_label_column(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGB", (960, 540), "white").save(p)
    out = make_sheet([[p], [p]], tmp_path / "cmp.png", labels=["A", "B"])
    assert Image.open(out).width == 56 + 16 + 480 + 16


def test_sheet_empty_middle_row_keeps_labels_aligned(tmp_path):
    import pytest
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (960, 540), (255, 0, 0)).save(a)
    Image.new("RGB", (960, 540), (0, 0, 255)).save(b)
    out = make_sheet([[a], [], [b]], tmp_path / "cmp.png", labels=["A", "B", "C"])
    im = Image.open(out)
    assert im.height == 16 + 2 * (270 + 16)  # the empty row is skipped
    # the second row is blue (originally the third row), and the label column (x<56) must have pixels that differ from the background because of the text
    assert im.getpixel((72 + 10, 16 + 286 + 10)) == (0, 0, 255)
    label_col = im.crop((0, 16 + 286, 56, 16 + 286 + 270)).convert("L")
    assert label_col.getextrema()[0] < 100  # "C" is drawn (it would be "B" if the labels had shifted)

    with pytest.raises(ValueError):
        make_sheet([[], []], tmp_path / "none.png")


def test_sheet_labels_shorter_than_rows(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGB", (960, 540), "white").save(p)
    out = make_sheet([[p], [p], [p]], tmp_path / "cmp.png", labels=["A"])
    assert Image.open(out).height == 16 + 3 * (270 + 16)


def test_sheet_label_column_fits_long_labels(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGB", (960, 540), "white").save(p)
    out = make_sheet([[p], [p]], tmp_path / "cmp.png", labels=["treat", "pattern"])
    im = Image.open(out).convert("RGB")
    first_thumb_x = im.width - 16 - 480
    from PIL import ImageFont
    text_end = 16 + ImageFont.load_default(size=22).getlength("pattern")
    assert text_end + 8 <= first_thumb_x  # the label stays clear of the first thumbnail
