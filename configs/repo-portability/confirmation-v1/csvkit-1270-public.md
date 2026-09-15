# Sudden switch small Number to DateTime.

Source: https://github.com/wireservice/csvkit/issues/1270

Hello,

The csvkit version is 1.5.0

> echo 13/12/2024, 5.5 | csvstat -H
>   1. "a"
> 
>         Type of data:          Text
>         Contains null values:  False
>         Non-null values:       1
>         Unique values:         1
>         Longest value:         10 characters
>         Most common values:    13/12/2024 (1x)
> 
>   2. "b"
> 
>         Type of data:          Number
>         Contains null values:  False
>         Non-null values:       1
>         Unique values:         1
>         Smallest value:        5.5
>         Largest value:         5.5
>         Sum:                   5.5
>         Mean:                  5.5
>         Median:                5.5
>         Most decimal places:   1
>         Most common values:    5.5 (1x)

Now I want to see Dates in the 1st column:

> echo 13/12/2024, 5.5 | csvstat -H --date-format "%d/%m/%Y"
 
> 1. "a"
> 
>         Type of data:          Date
>         Contains null values:  False
>         Non-null values:       1
>         Unique values:         1
>         Smallest value:        2024-12-13
>         Largest value:         2024-12-13
>         Most common values:    2024-12-13 (1x)
> 
>   2. "b"
> 
>         Type of data:          DateTime
>         Contains null values:  False
>         Non-null values:       1
>         Unique values:         1
>         Smallest value:        2025-05-05 00:00:00
>         Largest value:         2025-05-05 00:00:00
>         Most common values:    2025-05-05 00:00:00 (1x)

But now, I suddenly see a **datetime in the 2nd column**.
(If, however, I provide say 5.50 instead 5.5, or a larger number,  than that's still number.)

Should I upgrade to the recent version? 
Thanks.



Public acceptance clarification: an explicit date format must not turn ordinary decimal numbers into datetimes. Preserve explicitly configured datetime parsing and ordinary numeric inference.
