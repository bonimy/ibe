#include "../Wcs.hxx"
#include "../Cgi.hxx"

namespace ibe
{
void Wcs::pixelToSky (const double *pix, double *world)
{
  double imgcrd[2], phi[1], theta[1];
  int stat;
  int ret = ::wcsp2s (_wcs, 1, 2, pix, imgcrd, phi, theta, world, &stat);
  if (ret == 9)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "Invalid pixel coordinates");
    }
  else if (ret != 0)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to convert pixel coordinates to sky coordinates");
    }
  if (_wcs->lng != 0)
    {
      std::swap (world[0], world[1]);
    }
}
}
