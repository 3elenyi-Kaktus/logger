# Logger

### _by 3elenyi Kaktus_

Module with customizable logger.

## Internal logic

This module contains implementation of dual logger: console and file one. Since they are fully customizable, all data such as formatters and logger classes are loaded from python. All formatters must be inherited from `BaseFormatter` class.