# csvstack does not accept -z argument   => csv.field_size_limit

Source: https://github.com/wireservice/csvkit/issues/1219

csvstack -z 2500000 all.0000000*.csv.gz | gzip > all.final.csv.gz
TypeError: 'field_size_limit' is an invalid keyword argument for this function

Without -z argument:
Error: field larger than field limit (131072)

csvstack --version
csvstack 1.1.1

Public acceptance clarification: csvstack -z/--maxfieldsize must accept a limit for both ordinary and over-default-limit fields. Preserve normal stacking. The shared DictReader setup is also used by csvpy.
