import subprocess, logging, os, errno, codecs, shutil
from itertools import chain
from pelican import signals
from pelican.readers import BaseReader, pelican_open
from pelican.generators import PagesGenerator
from pelican.contents import Page, is_valid_content

try:
    from markdown import Markdown
except ImportError:
    Markdown = False


logger = logging.getLogger(__name__)


class SlateReader(BaseReader):
    enabled = True
    file_extensions = ['md', 'markdown', 'mkd', 'mdown']

    def __init__(self, *args, **kwargs):
        super(SlateReader, self).__init__(*args, **kwargs)
        self.extensions = list(self.settings['MD_EXTENSIONS'])
        if 'meta' not in self.extensions:
            self.extensions.append('meta')

    def markdown_read(self, source_path):

        md = Markdown(extensions=self.extensions)
        with pelican_open(source_path) as text:
            content = md.convert(text)

        metadata = {}
        for name, value in md.Meta.items():
            name = name.lower()
            if name == "summary":
                summary_values = "\n".join(value)
                md.reset()
                summary = md.convert(summary_values)
                metadata[name] = self.process_metadata(name, summary)
            elif len(value) > 1:
                metadata[name] = self.process_metadata(name, value)
            else:
                metadata[name] = self.process_metadata(name, value[0])

        return content, metadata

    def read(self, source_path):

        source = codecs.open(source_path, 'r')

        metadata = {}
        line = source.readline()
        while ( line.strip() != "" ):
            name = line.split(":")[0].strip().lower()
            value = line.split(":")[1].strip()
            metadata[name] = self.process_metadata(name, value)
            line = source.readline()

        content = source.read()
        source.close()

        if not ('slate' in metadata and metadata['slate'].lower() == 'true'):
            if ( bool(Markdown) ):
                return self.markdown_read(source_path)

        slate_content = codecs.open('slate/source/index.md', 'w')
        slate_content.write(content)
        slate_content.close()
        os.chdir(os.path.join(os.getcwd(), "slate"))

        p = subprocess.Popen(
            ['bundle', 'exec', 'middleman', 'build', '--clean'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = p.communicate()
        if ( p.returncode != 0 ):
            logger.warning('Slate page {} building process failed!'.format(source_path))
            raise Exception(err)

        slate_content = codecs.open('build/index.html', 'r')
        processed = slate_content.read()
        processed = processed.decode('utf-8')
        slate_content.close()
        os.chdir("../")

        return processed, metadata

def add_reader(readers):
    readers.reader_classes['slate'] = SlateReader

def register():
    signals.readers_init.connect(add_reader)

class SlatePage(Page):
    default_template = 'slate_page'

class SlateGenerator(PagesGenerator):

    def __init__(self, pages_generator):
        self.generator = pages_generator

    def generate(self):

        slate_pages = False
        help(self.generator.get_files)
        for f in self.generator.get_files(
            self.generator.settings['SLATE_PAGES_DIR']):
            try:

                page = self.generator.readers.read_file(
                    base_path = self.generator.path, path = f,
                    content_class = SlatePage, context = self.generator.context)

            except Exception as e:
                logger.warning('Could not process {}\n{}'.format(f, e))
                continue
            else:

                self.generator.add_source_path(page)

                if page.status == "published":
                    self.generator.pages.append(page)
                    slate_pages = True
                else:
                    logger.warning("Unknown status %s for file %s," +
                        " skipping it." % (repr(page.status), repr(f)))

        if ( slate_pages ):
            if ( os.path.exists("output/theme/vendor/slate") ):
                shutil.rmtree("output/theme/vendor/slate")
            shutil.copytree("slate/build/theme/vendor/slate",
                "output/theme/vendor/slate")

        self.generator._update_context(('pages', ))
        self.generator.context['PAGES'] = self.generator.pages

def generate_slate_pages_too(pelican_object):
    slate_generator = SlateGenerator(pelican_object)
    slate_generator.generate()

signals.page_generator_finalized.connect(generate_slate_pages_too)
