fossilpy
========
Simple pure-python library for reading Fossil repositories.

.. code-block:: pycon

   >>> r = Repo('project.fossil')
   >>> f = r.file(123)
   >>> f.blob
   b'File content...'
   >>> filelist = r.manifest(124).F
   >>> filelist
   [('file', '1234567890aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')]

This is a thin wrapper, and Fossil is an SQLite-based version control system.
So using raw SQL (``Repo.execute``) may be necessary to get more information.

Writing, committing, or executing Fossil commands is not supported. (Although you can do SQL, writing is not recommended.) Reading the config database (~/.fossil), the checkout database (_FOSSIL_), or the checkout directory is also not supported.

API
---

Classes
~~~~~~~

- **Repo(repository, check=False, cachesize=64)**: Represents a Fossil repo. ``repository`` is the file name. ``check`` specifies whether to calculate checksum. If numpy is not installed, calculation will be much slower. ``cachesize`` specifies how much blobs should be cached, set to 0 to disable.

  - Repo.\ **file(self, key)**: Returns a ``File`` according to the ``key``, which is either the blob's rid or uuid (SHA1/SHA3-256).

  - Repo.\ **manifest(self, key)**: Returns a ``StructuralArtifact`` according to the ``key``.

  - Repo.\ **artifact(self, key, type_=None)**: Returns an ``Artifact`` according to the ``key``. ``type_`` can be ``'structural'`` or ``'file'``.

  - Repo.\ **__getitem__(self, key)**: Returns an ``Artifact`` according to the ``key``.

  - Repo.\ **find_artifact(self, prefix)**: Given the uuid (SHA1/SHA3-256) prefix, returns a tuple ``(rid, uuid)``. If not found, raises a ``KeyError``.

  - Repo.\ **to_uuid(self, rid)**: Given the rid, returns the uuid of a blob. If not found, raises an ``IndexError``.

  - Repo.\ **to_rid(self, uuid)**: Given the uuid, returns the rid of a blob. If not found, raises an ``IndexError``.

  - Repo.\ **execute(self, sql, parameters=None)**: Execute raw SQL statements on the Fossil repo (SQLite database). See also `src/schema.c <https://www.fossil-scm.org/index.html/artifact/f72846e4a8e2929f>`_.

- **Artifact(blob=None, rid=None, uuid=None)**: Represents a Fossil artifact, which is anything inside the ``blob`` table. Has attributes ``blob``, ``rid`` and ``uuid``. ``blob`` is the artifact(file) content.

- **File(blob=None, rid=None, uuid=None)**: Represents a file, same as ``Artifact``.

- **StructuralArtifact(blob=None, rid=None, uuid=None)**: Represent a structural artifact, aka. manifest, can be such as check-in, wiki and tickets.

  - StructuralArtifact.\ **keys()**: List cards.
  - StructuralArtifact.\ **cards**: Dictionary of cards. If a card type can occur multiple times, cards of the same type are stored in a list.
  - Cards can be accessed like ``art.F``, ``art['F']`` or ``art.file``. See also `Fossil documentation <https://www.fossil-scm.org/index.html/doc/trunk/www/fileformat.wiki#structural>`_. Some useful cards: F(file), C(comment), P(parent_artifact), U(user_login), D(datetime), W(wiki_text)


Misc.
~~~~~

- **LRUCache(maxlen)**: A simple implementation of least recently used (LRU) cache.

Fossil uses Julian date in most tables.

- **julian_to_unix(t)**: Convert Julian date ``t`` to unix timestamp.
- **unix_to_julian(t)**: Convert unix timestamp ``t`` to Julian date.

