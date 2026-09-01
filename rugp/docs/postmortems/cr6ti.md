# Cr6Ti extent correction

## Symptom

An early runtime candidate redirected one byte more than the serialized Cr6Ti
object. It displayed because the decoder obeyed the payload length and ignored
the trailing zero, but “the game tolerated it” was not an exact format proof.

## Controlled audit

The standard records in the PF image authority use:

```text
0x2C-byte header + payload_length bytes + 00 00 trailer
```

Archive-unit alignment follows the record physically, but is not part of the
record extent stored in a RIO directory or RUO redirect. For the controlled
QuickSave replacement the values were:

```text
header                 44
payload             26,821
serialized trailer       2
record extent        26,867
placement padding         1
placement span       26,868
```

A read-only census of 533 PF must-translate Cr6Ti records found 531 standard
records with a two-byte zero trailer: 433 kind3/flags7, 44 kind2/flags7 and 54
kind2/flags15. The remaining two were a distinct legacy 0x28-byte
kind2/flags3 profile with no trailer. All 533 computed extents matched the
independent catalog extents.

## Production rule

- Compute serialized extent from the identified profile; never include generic
  archive alignment.
- Treat the two legacy records as explicit exceptions, not evidence that the
  standard trailer is optional.
- Decode official input, encode candidate, decode independently, and compare
  full RGBA plus consumed payload bytes before building a RUO.

The strict implementation and synthetic regression tests live in
[`rugp/formats/images/`](../../formats/images/README.md). Runtime tolerance is
recorded as historical evidence, not promoted into the writer contract.
