#pragma once

#include "fitsio.h"
#include <string>
extern "C" {
#include "fitsio2.h"
}


namespace ibe
{
/// RAII wrapper for a ::fitsfile pointer.
class FitsFile
{
public:
  FitsFile (char const *path);
  ~FitsFile ();

  // conversion operators
  operator ::fitsfile *() { return _file; }
  operator ::fitsfile const *() { return _file; }

private:
  FitsFile (FitsFile const &);
  FitsFile &operator=(FitsFile const &);

  ::fitsfile *_file;
};
}
