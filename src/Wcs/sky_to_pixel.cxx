#include "../Wcs.hxx"
#include "../Cgi.hxx"

namespace ibe
{
void Wcs::sky_to_pixel (const double *sky, double *pix)
{
  int off_scale;
  wcsc2pix (_wcs, sky[0], sky[1], const_cast<char *>("ICRS"), &(pix[0]),
            &(pix[1]), &off_scale);

  if (off_scale == 1)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to convert sky coordinates to pixel coordinates");
    }
}
}
