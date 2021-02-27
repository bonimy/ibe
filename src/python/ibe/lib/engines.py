import lxml.etree as etree
import sqlalchemy

import ibe.lib.utils as utils


class Engine(object):
    """A thin wrapper around a sqlalchemy Engine and MetaData object.
    These underlying objects are constructed based on configuration
    data from an XML element - use the readEngines() function to create
    an Engine from an XML file.
    """
    def __init__(self, element):
        self.id = element.get("id")
        self.echo = False
        if "echo" in element.attrib:
            self.echo = utils.xs_bool(element.get("echo"))
        self.echo_pool = False
        if "echo_pool" in element.attrib:
            self.echo_pool = utils.xs_bool(element.get("echo_pool"))
        self.pool_recycle = -1
        if "pool_recycle" in element.attrib:
            self.pool_recycle = int(element.get("pool_recycle"))
        self.url = element[0].text
        self.paramstyle = element[1].text
        # For now, create engines eagerly
        self._sa_engine = sqlalchemy.create_engine(self.url,
                                                   echo=self.echo,
                                                   echo_pool=self.echo_pool,
                                                   pool_recycle=self.pool_recycle,
                                                   paramstyle=self.paramstyle)
        self._sa_engine.execution_options(autocommit=False)
        def no(*args, **kw):
            return False
        if not self.echo:
            # HACK: echo = False still results in a ton of log messages
            self._sa_engine._should_log_info = no
            self._sa_engine._should_log_debug = no 
        self._sa_meta = sqlalchemy.MetaData(bind=self._sa_engine)
        self._sa_inspector = sqlalchemy.inspect(self._sa_engine)

    def metadata(self):
        """Returns the sqlalchemy MetaData object for the database
        underlying this Engine.
        """
        return self._sa_meta

    def engine(self):
        """Returns the sqlalchemy Engine object for this Engine.
        """
        return self._sa_engine

    def table(self, dbname):
        """Returns the sqlalchemy Table for the table with the specified name.
        """
        kw = { 'autoload': True }
        if self.url.startswith('oracle'):
            kw['oracle_resolve_synonyms'] = True
            kw['schema'] = self._sa_inspector.default_schema_name
        return sqlalchemy.Table(dbname, self._sa_meta, **kw)

    def connect(self):
        """Returns a newly allocated Connection object for the database
        underlying this Engine.
        """
        return self._sa_engine.connect()


def readEngines(engines_file, engines_schema, engines=None):
    """Reads a configuration file describing a set of database engines.
    Returns a dict mapping engine IDs to Engine objects.

    - engines_file:   Path or file-like object for the XML configuration file.
    - engines_schema: Path of file-like object for the XML configuration file
                      schema.
    - engines:        An optional dictionary mapping database engine IDs
                      (strings) to Engine objects. Engines from the
                      configuration file will be added to this dictionary;
                      it is a RuntimeError for configuration files to define
                      multiple engines with the same ID.
    """
    engines = engines or {}
    if not isinstance(engines, dict):
        raise TypeError(str.format('engines: expecting a dict, got {0}.{1}',
                        type(engines).__module__, type(engines).__name__))
    # Read schema, read and validate configuration file
    xml_schema_doc = etree.parse(engines_schema)
    xml_schema = etree.XMLSchema(xml_schema_doc)
    doc = etree.parse(engines_file)
    xml_schema.assertValid(doc)
    # Build engine configuration
    for element in doc.getroot().iterchildren(tag='engine'):
        eid = element.get("id")
        if eid in engines:
            raise RuntimeError(str.format(
                "Duplicate definition for engine {0}:\n{1}",
                eid, etree.tostring(element)))
        engines[eid] = Engine(element)
    return engines
