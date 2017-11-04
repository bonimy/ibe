#include "Cgi.hxx"

#include "fitsio.h"

namespace ibe
{
// Check if CFITSIO has failed and throw an internal server error if so.
void checkFitsError (int status)
{
  char statMsg[32];
  char errMsg[96];
  if (status != 0)
    {
      fits_get_errstatus (status, statMsg);
      if (fits_read_errmsg (errMsg) != 0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             format ("%s : %s", statMsg, errMsg));
        }
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR, statMsg);
    }
}
}
