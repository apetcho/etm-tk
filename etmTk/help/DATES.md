# Dates

## Fuzzy dates

When either a *datetime* or an *time period* is to be entered, special formats are used in *etm*. Examples include entering a starting datetime for an item using `@s`, jumping to a date using Ctrl-J and calculating a date using F5.

Suppose, for example, that it is currently 8:30am on Friday, February 15, 2013. Then, *fuzzy dates* would expand into the values illustrated below.

        mon 2p or mon 14h    2:00pm Monday, February 19
        fri                  12:00am Friday, February 15
        9a -1/1 or 9h -1/1   9:00am Tuesday, January 1
        +2/15                12:00am Monday, April 15 2013
        8p +7 or 20h +7      8:00pm Friday, February 22
        -14                  12:00am Friday, February 1
        now                  8:30am Friday, February 15

Note that 12am is the default time when a time is not explicity entered. E.g., `+2/15` in the examples above gives 12:00am on April 15.

To avoid ambiguity, always append either 'a', 'p' or 'h' when entering an hourly time, e.g., use `1p` or `13h`.

## Time periods

Time periods are entered using the format `DdHhMm` where D, H and M are integers and d, h and m refer to days, hours and minutes respectively. For example:

        2h30m                2 hours, 30 minutes
        7d                   7 days
        45m                  45 minutes

As an example, if it is currently 8:50am on Friday February 15, 2013, then entering `now + 2d4h30m` into the date calculator would give `2013-02-17 1:20pm`.

## Time zones

Dates and times are always stored in *etm* data files as times in the time zone given by the entry for `@z`. On the other hand, dates and times are always displayed in *etm* using the local time zone of the system.

For example, if it is currently 8:50am EST on Friday February 15, 2013, and an item is saved on a system in the `US/Eastern` time zone containing the entry

    @s now @z Australia/Sydney

then the data file would contain

    @s 2013-02-16 12:50am @z Australia/Sydney

but this item would be displayed as starting at ` 8:50am 2013-02-15` on the system in the `US/Eastern` time zone.

## Anniversary substitutions

An anniversary substitution is an expression of the form `!YYYY!` that appears in an item summary. Consider, for example, the occassion

    ^ !2010! anniversary @s 2011-02-20 @r y

This would appear on Feb 20 of 2011, 2012, 2013 and 2014, respectively, as *1st anniversary*, *2nd anniversary*, *3rd anniversary* and *4th anniversary*. The suffixes, *st*, *nd* and so forth, depend upon the translation file for the locale.
