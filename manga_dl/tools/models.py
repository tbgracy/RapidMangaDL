import os


class URLFile:
    def __init__(self, url, filepath, *args, **kwargs):
        self.url = url
        self.filepath = filepath

    @property
    def filename(self):
        return os.path.basename(self.filepath)

    # for url,filename = urlfile
    def __iter__(self):
        return iter([self.url, self.filename])

    def __repr__(self):
        return f"URLFile(url={self.url}, filepath={self.filepath})"

    def __str__(self):
        return self.filepath

    def __getitem__(self, key):
        if isinstance(key, int):
            if key == 0:
                return self.url
            elif key == 1:
                return self.filename
            elif key == 2:
                return self.filepath
            else:
                raise IndexError("URLFile index out of range")
        else:
            raise TypeError("URLFile indices must be integers")

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if key == 0:
                self.url = value
            elif key == 2:
                self.filepath = value
            else:
                raise IndexError("URLFile index out of range")
        else:
            raise TypeError("URLFile indices must be integers")
        
        

