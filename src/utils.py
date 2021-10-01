

class ExportFile:
    def __init__(self, data, file_path, format_type="plain_text", lang=None):
        self.data = data
        self.format = format_type
        self.file_path = file_path
        self.lang = lang

    def export(self):
        if self.format == "plain_text":
            file_obj = open(f'{self.file_path}.txt', "w")
            file_obj.writelines(self.data)
            file_obj.close()

        return True
