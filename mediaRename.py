import os
from datetime import datetime
import struct
import sys
import pytz
from PIL import Image
from PIL.ExifTags import TAGS
import pyheif
import piexif

class MediaRename(object):

    def __init__(self, directory):
        self.directory = directory if directory else './'
        self.fileFormat = "%Y-%m-%d %H.%M.%S"
        self.timeZone = "Europe/Madrid"

    def changeToLower(self):
        for file in os.listdir(self.directory):
            path = os.path.join(self.directory, file)
            os.rename(
                path,
                path.lower()
            )

    def getFileList(self):
        return [file for file in os.listdir(self.directory)]

    def filePath(self, file):
        return os.path.join(self.directory, file)

    def apply_tz(self, date):
        tz = pytz.timezone(self.timeZone)
        offset = tz.utcoffset(date)
        return tz.localize(date) + offset

    def renameFile(self, filename, extension, filepath, formatTime):
        formatTime_string = formatTime.strftime(self.fileFormat)
        if filename.startswith(formatTime_string):
            return
        
        newfile = formatTime_string + extension.lower()
        nameFound = False
        count = 1
        while not nameFound:
            if newfile in self.getFileList():
                newfile = "%s-%s%s" % (formatTime_string, count, extension.lower())
                count += 1
            else:
                nameFound = True

        os.rename(filepath, self.filePath(newfile))
        print(("%s%s" % (filename, extension)).rjust(35) + '    =>    ' + newfile.ljust(35))
        return True

    def getMOVDateTime(self, filename):
        atomHeaderSize = 8
        creationTime = None
        # search for moov item
        with open(filename, "rb") as f:
            while True:
                atomHeader = f.read(atomHeaderSize)
                if atomHeader[4:8] == b'moov':
                    break  # found
                else:
                    atomSize = struct.unpack('>I', atomHeader[0:4])[0]
                    f.seek(atomSize - 8, 1)

            # found 'moov', look for 'mvhd' and timestamps
            atomHeader = f.read(atomHeaderSize)
            if atomHeader[4:8] == b'cmov':
                raise RuntimeError('moov atom is compressed')
            elif atomHeader[4:8] != b'mvhd':
                raise RuntimeError('expected to find "mvhd" header.')
            else:
                f.seek(4, 1)
                creationTime = struct.unpack('>I', f.read(4))[0] - 2082844800 # QuickTime Epoch Adjuster
                creationTime = datetime.fromtimestamp(creationTime)
                if creationTime.year < 1990:  # invalid or censored data
                    creationTime = None

                return creationTime

    def processMOVFiles(self):
        renamed = 0
        for file in self.getFileList():
            filename, extension = os.path.splitext(file)
            filepath = self.filePath(file)
            if extension.lower() in [".mp4", ".mov"]:
                formatTime = self.getMOVDateTime(filepath)
                if formatTime:
                    if self.renameFile(filename, extension, filepath, formatTime):
                        renamed += 1

        print('%s mov/mp4 files are renamed.\n' % renamed)

    def getJPGDateTime(self, file):
        img = Image.open(file)._getexif()
        if img:
            for (k, v) in img.items():
                if TAGS.get(k) == "DateTimeDigitized":
                    return v

    def processJPGFiles(self):
        renamed = 0
        for file in self.getFileList():
            filename, extension = os.path.splitext(file)
            filepath = self.filePath(file)
            if extension.lower() in [".jpg", ".jpeg"]:
                dateTimeDigitalized = self.getJPGDateTime(filepath)
                if dateTimeDigitalized:
                    formatTime = datetime.strptime(dateTimeDigitalized, "%Y:%m:%d %H:%M:%S")
                    if self.renameFile(filename, extension, filepath, formatTime):
                        renamed += 1

        print('%s jpg files are renamed.\n' % renamed)

    def getHEICDateTime(self, filepath):
        with open(filepath, "rb") as f:
            data = f.read()
            i = pyheif.read_heif(data)
            for metadata in i.metadata or []:
                if metadata.get("type") == "Exif":
                    exif_dict = piexif.load(metadata.get("data"))
                    return (
                        exif_dict.get("0th").get(306).decode("utf-8") 
                        if exif_dict.get("0th") and exif_dict.get("0th").get(306)
                        else None
                    )

    def processHEICFiles(self):
        renamed = 0
        for file in self.getFileList():
            filename, extension = os.path.splitext(file)
            filepath = self.filePath(file)
            if extension.lower() == ".heic":
                dateTimeDigitalized = self.getHEICDateTime(filepath)
                if dateTimeDigitalized:
                    formatTime = datetime.strptime(dateTimeDigitalized, "%Y:%m:%d %H:%M:%S")
                    if self.renameFile(filename, extension, filepath, formatTime):
                        renamed += 1

        print('%s heic files are renamed.\n' % renamed)

    def main(self):
        self.changeToLower()
        self.processMOVFiles()
        self.processJPGFiles()
        self.processHEICFiles()


if __name__ == '__main__':
    MediaRename(
        directory=sys.argv[1] if len(sys.argv) > 1 else None
    ).main()