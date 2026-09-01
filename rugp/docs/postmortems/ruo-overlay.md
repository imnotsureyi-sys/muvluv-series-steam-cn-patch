# RUO overlay: what the loader actually redirects

## Result

An rUGP RUO is not a second directory tree for the game. For an existing RIO
object, it stores a complete replacement record and maps the old encoded object
offset to the new RUO offset and size. The old physical extent therefore does
not cap the replacement. No ICI or directory edit is needed when the logical
path already exists.

```text
[replacement records and alignment padding]
[N redirect records, 12 bytes each]
[N as little-endian uint32]

redirect = source_raw_offset, target_raw_offset, replacement_raw_size
```

The loader reads `N` from EOF, rejects only implausibly large counts, then
loads the preceding `N * 12` bytes. There is no RUO magic, header, version,
checksum or separate TOC. Encoded offsets/sizes use the same bias and archive
unit contract as the base game; PF/PM use four-byte units, while the audited
Muv/Alternative builds use two-byte units.

## How this was established

Static executable analysis identified the wildcard scan, RUO loader and
redirect resolver. A one-record PF overlay was then decoded back field by
field. In an isolated runtime test the exact redirect appeared once in the
process's private redirect-map memory and the RUO filename appeared in private
memory, proving that the running loader opened the file and copied its footer.
An independent file-open probe also observed the real PF process opening the
matching RUO basename.

## The multiple-RUO trap

The games enumerate multiple `.ruo*` files, but the redirect entry contains no
archive ID. The manager retains one final RUO archive index while the redirect
map is global; every entry is resolved against that last archive. Independent
RUO files are therefore not safely stackable.

- PF/PM originally have no RUO: deploy one cumulative `base.rio.ruo1`.
- Titles that already ship an official RUO: preserve its data region and
  redirects, append localized records, replace duplicate source keys, then
  write one combined footer.

[`rugp/formats/rio/ruo.py`](../../formats/rio/ruo.py) implements the reviewed
parser/writer contract. Synthetic tests cover encoded units, footer bounds,
duplicate-key replacement and cumulative layout without redistributing game
records.

## Boundary

This proves replacement of existing object identities. Adding/removing paths
or changing directory topology still requires a directory/root strategy. A
valid RUO file also does not prove that every replacement record is a valid
CRsa/Cr6Ti/CRip object; codec round-trip and in-game QA remain separate gates.
