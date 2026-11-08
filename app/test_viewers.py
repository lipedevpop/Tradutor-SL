import tempfile
import unittest
from pathlib import Path
from log_reader import LogReader, parse_line
from viewer_profiles import browse_start

class ViewerTests(unittest.TestCase):
    def test_firestorm_optional_time_and_datestamped_names(self):
        for stamp in ('[2026/10/1 9:05]  ', '[9:05]  ', '[9:05:12 PM]  ', ''):
            with self.subTest(stamp=stamp):
                msg=parse_line(stamp+'Rose (rose.resident): hi', 'rose resident-2026-10')
                self.assertIsNotNone(msg)
                self.assertEqual(msg.text, 'hi')

    def test_cool_legacy_names_dates_and_without_resident(self):
        for stamp in ('[01/10/2026 21:30] ', '[2026-10-01 21:30:03] ', '[9:30 PM] ', ''):
            for name in ('Rose Resident', 'rose resident-2026-10', 'rose-2026-10'):
                with self.subTest(stamp=stamp,name=name):
                    msg=parse_line(stamp+'Rose Resident: not much',name)
                    self.assertIsNotNone(msg)
                    self.assertEqual(msg.text,'not much')

    def test_timestamp_options_keep_exclusions(self):
        for stamp in ('[9:05] ', ''):
            self.assertIsNone(parse_line(stamp+'You: hello','rose'))
            self.assertIsNone(parse_line(stamp+'My Avatar: hello','my_avatar',['my_avatar']))
            self.assertIsNone(parse_line(stamp+'Rose: hello','some (group)'))
            self.assertIsNone(parse_line(stamp+'Rose: hello','rose conference'))
            self.assertIsNone(parse_line(stamp+'Rose: hello','chat'))
            self.assertIsNone(parse_line(stamp+'Rose: https://example.com','rose'))
        self.assertIsNone(parse_line(' Rose: continuation is not a new IM','rose'))
        self.assertIsNone(parse_line('[21:00] Rose is Offline','rose'))

    def test_new_private_logs_for_each_viewer_and_no_old_history(self):
        for filename,line in (
            ('rose_resident.txt','[2026/10/01 21:30] Rose (rose.resident): hi'),
            ('rose resident-2026-10.txt','[9:30 PM]  Rose (rose.resident): hello'),
            ('Rose Resident.txt','Rose Resident: not much')):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as d:
                folder=Path(d); path=folder/filename
                path.write_text(line+'\n',encoding='utf-8')
                reader=LogReader(folder)
                self.assertEqual(reader.poll(),[])
                with path.open('a',encoding='utf-8') as f:f.write(line+'\n')
                self.assertEqual(len(reader.poll()),1)
                self.assertEqual(reader.poll(),[])

    def test_viewer_folder_hints_and_custom_folder(self):
        with tempfile.TemporaryDirectory() as d:
            appdata=Path(d)
            for viewer,dirname in [('Alchemy','AlchemyNext'),('Firestorm','Firestorm_x64'),('Cool VL Viewer','SecondLife')]:
                (appdata/dirname).mkdir()
                self.assertEqual(browse_start(viewer,appdata=d),appdata/dirname)
            custom=appdata/'custom_logs';custom.mkdir()
            self.assertEqual(browse_start('Firestorm',str(custom),d),custom)

class DetectionTests(unittest.TestCase):
    def test_each_viewer_standard_avatar_folder(self):
        from viewer_profiles import discover_folders
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for viewer,dirname in [('Alchemy','AlchemyNext'),('Firestorm','Firestorm_x64'),('Cool VL Viewer','SecondLife')]:
                avatar=root/dirname/'my_avatar';avatar.mkdir(parents=True)
                (avatar/'rose resident.txt').write_text('')
                self.assertEqual(discover_folders(viewer,d),[avatar])

    def test_custom_path_from_viewer_preferences(self):
        from viewer_profiles import discover_folders
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            avatar=root/'SecondLife'/'my_avatar';avatar.mkdir(parents=True)
            logs=root/'custom'/'my_avatar';logs.mkdir(parents=True)
            (logs/'Rose Resident.txt').write_text('')
            settings=ET.Element('llsd');mapping=ET.SubElement(settings,'map')
            ET.SubElement(mapping,'key').text='InstantMessageLogPath'
            value=ET.SubElement(mapping,'map');ET.SubElement(value,'key').text='Value'
            ET.SubElement(value,'string').text=str(logs.parent)
            ET.ElementTree(settings).write(avatar/'settings_per_account_coolvlviewer.xml')
            self.assertEqual(discover_folders('Cool VL Viewer',d),[logs])

    def test_multiple_avatars_return_choices(self):
        from viewer_profiles import discover_folders
        with tempfile.TemporaryDirectory() as d:
            folders=[]
            for name in ('first_resident','second_resident'):
                folder=Path(d)/'Firestorm_x64'/name;folder.mkdir(parents=True)
                (folder/'friend.txt').write_text('');folders.append(folder)
            self.assertEqual(discover_folders('Firestorm',d),sorted(folders))

    def test_missing_and_malformed_settings_are_nonfatal(self):
        from viewer_profiles import discover_folders
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(discover_folders('Firestorm',d),[])
            path=Path(d)/'Firestorm_x64'/'user_settings';path.mkdir(parents=True)
            (path/'settings.xml').write_text('<invalid')
            self.assertEqual(discover_folders('Firestorm',d),[])

    def test_does_not_scan_unrelated_directories_or_read_transcripts(self):
        from viewer_profiles import discover_folders
        with tempfile.TemporaryDirectory() as d:
            other=Path(d)/'Documents'/'my_avatar';other.mkdir(parents=True)
            (other/'friend.txt').write_text('private message')
            self.assertEqual(discover_folders('Firestorm',d),[])
