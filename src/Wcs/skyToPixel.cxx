#include "../Wcs.hxx"
#include "../Cgi.hxx"

namespace ibe
{
void Wcs::skyToPixel (const double *sky, double *pix)
{
  double imgcrd[2], phi[1], theta[1], world[2];
  int stat, ret;
  world[_wcs->lng] = sky[0];
  world[_wcs->lat] = sky[1];
  ret = ::wcss2p (_wcs, 1, 2, world, imgcrd, phi, theta, pix, &stat);
  if (ret == 9)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "Invalid sky coordinates");
    }
  else if (ret != 0)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to convert sky coordinates to pixel coordinates");
    }
}
}
