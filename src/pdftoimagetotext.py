from pdf2image import convert_from_path
import os


def pdf_to_image(pdf_path, first_page=None, last_page=None):
    if first_page and last_page:
        pages = convert_from_path(pdf_path, 200, first_page=first_page, last_page=last_page)
    else:
        pages = convert_from_path(pdf_path, 200)
    image_path_all = list()
    dir_path = pdf_path.split(".")[0]
    isdir = os.path.isdir(dir_path)
    file_name = str(dir_path).split("/")[-1]

    if not isdir:
        os.mkdir(dir_path)

    for count, page in enumerate(pages, first_page):
        temp_file_name = pdf_path.split(".")[0]
        filename = f"{temp_file_name}/{file_name}_page_" + str(count) + ".jpg"
        page.save(filename, 'JPEG')
        image_path_all.append(filename)

    return image_path_all


