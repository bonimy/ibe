import abc
import math
import numpy
import operator
import pywcs
import sys

# Unit conversion factors
ARCSEC_PER_DEG = 3600.0
DEG_PER_ARCSEC = 1.0 / 3600.0

# Angle comparison slack
ANGLE_EPSILON = 0.001 * DEG_PER_ARCSEC # 1 milli-arcsec in degrees

# Used in pole proximity tests
POLE_EPSILON = 1.0 * DEG_PER_ARCSEC # 1 arcsec in degrees

# Dot product of 2 cartesian unit vectors must be < COS_MAX,
# or they are considered degenerate.
COS_MAX = 1.0 - 1.0e-15

# Square norm of the cross product of 2 cartesian unit vectors must be
# >= CROSS_N2MIN, or the edge joining them is considered degenerate
CROSS_N2MIN = 2e-15

# Dot product of a unit plane normal and a cartesian unit vector must be
# > SIN_MIN, or the vector is considered to be on the plane
SIN_MIN = math.sqrt(CROSS_N2MIN)

# Constants related to floating point arithmetic
INF = float('inf')
NEG_INF = float('-inf')
MIN_FLOAT = sys.float_info.min
EPSILON = sys.float_info.epsilon


# -- Utility methods ----

def dot(v1, v2):
    """Returns the dot product of cartesian 3-vectors v1 and v2.
    """
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]

def cross(v1, v2):
    """Returns the cross product of cartesian 3-vectors v1 and v2.
    """
    return (v1[1] * v2[2] - v1[2] * v2[1],
            v1[2] * v2[0] - v1[0] * v2[2],
            v1[0] * v2[1] - v1[1] * v2[0])

def invScale(v, s):
    """Returns a copy of the cartesian 3-vector v scaled by 1 / s.
    """
    return (v[0] / s, v[1] / s, v[2] / s)

def normalize(v):
    """Returns a normalized copy of the cartesian 3-vector v.
    """
    n = math.sqrt(dot(v, v))
    if n == 0.0:
        raise RuntimeError('Cannot normalize a 3-vector with 0 magnitude')
    return (v[0] / n, v[1] / n, v[2] / n)

def sphericalCoords(*args):
    """Returns spherical coordinates in degrees for the input coordinates,
    which can be spherical or 3D cartesian. The 2 (spherical) or 3
    (cartesian 3-vector) inputs can be passed either individually
    or as a tuple/list, and can be of any type convertible to a float.
    """
    if len(args) == 1:
        args = args[0]
    if len(args) == 2:
        t = (float(args[0]), float(args[1]))
        if t[1] < -90.0 or t[1] > 90.0:
            raise RuntimeError('Latitude angle is out of bounds')
        return t
    elif len(args) == 3:
        x = float(args[0])
        y = float(args[1])
        z = float(args[2])
        d2 = x * x + y * y
        if d2 == 0.0:
            theta = 0.0
        else:
            theta = math.degrees(math.atan2(y, x))
            if theta < 0.0:
                theta += 360.0
        if z == 0.0:
            phi = 0.0
        else:
            phi = math.degrees(math.atan2(z, math.sqrt(d2)))
        return (theta, phi)
    raise TypeError('Expecting 2 or 3 coordinates, or a tuple/list ' +
                    'containing 2 or 3 coordinates')

def unitVector(*args):
    """Returns a unit cartesian 3-vector corresponding to the input
    coordinates, which can be spherical or 3D cartesian. The 2 (spherical)
    or 3 (cartesian 3-vector) input coordinates can either be passed
    individually or as a tuple/list, and can be of any type convertible
    to a float.
    """
    if len(args) == 1:
        args = args[0]
    if len(args) == 2:
        theta = math.radians(float(args[0]))
        phi = math.radians(float(args[1]))
        cosPhi = math.cos(phi)
        return (math.cos(theta) * cosPhi,
                math.sin(theta) * cosPhi,
                math.sin(phi))
    elif len(args) == 3:
        x = float(args[0])
        y = float(args[1])
        z = float(args[2])
        n = math.sqrt(x * x + y * y + z * z)
        if n == 0.0:
            raise RuntimeError('Cannot normalize a 3-vector with 0 magnitude')
        return (x / n, y / n, z / n)
    raise TypeError('Expecting 2 or 3 coordinates, or a tuple/list ' +
                    'containing 2 or 3 coordinates')

def sphericalAngularSep(p1, p2):
    """Returns the angular separation in degrees between points p1 and p2,
    which must both be specified in spherical coordinates. The implementation
    uses the halversine distance formula.
    """
    sdt = math.sin(math.radians(p1[0] - p2[0]) * 0.5)
    sdp = math.sin(math.radians(p1[1] - p2[1]) * 0.5)
    cc = math.cos(math.radians(p1[1])) * math.cos(math.radians(p2[1]))
    s = math.sqrt(sdp * sdp + cc * sdt * sdt)
    if s > 1.0:
        return 180.0
    else:
        return 2.0 * math.degrees(math.asin(s))

def clampPhi(phi):
    """Clamps the input latitude angle phi to [-90.0, 90.0] deg.
    """
    if phi < -90.0:
        return -90.0
    elif phi >= 90.0:
        return 90.0
    return phi

def reduceTheta(theta):
    """Range reduces the given longitude angle to lie in the range
    [0.0, 360.0).
    """
    theta = math.fmod(theta, 360.0)
    if theta < 0.0:
        return theta + 360.0
    else:
        return theta

def northEast(v):
    """Returns unit N,E basis vectors for a point v, which must be a
    cartesian 3-vector.
    """
    north = (-v[0] * v[2],
             -v[1] * v[2],
             v[0] * v[0] + v[1] * v[1])
    if north == (0.0, 0.0, 0.0):
        # pick an arbitrary orthogonal basis with z = 0
        north = (-1.0, 0.0, 0.0)
        east = (0.0, 1.0, 0.0)
    else:
        north = normalize(north)
        east = normalize(cross(north, v))
    return north, east

def alpha(r, centerPhi, phi):
    """Returns the longitude angle alpha of the intersections (alpha, phi),
    (-alpha, phi) of the circle centered on (0, centerPhi) with radius r and
    the plane z = sin(phi). If there is no intersection, None is returned.
    """
    if phi < centerPhi - r or phi > centerPhi + r:
        return None
    a = abs(centerPhi - phi)
    if a <= r - (90.0 - phi) or a <= r - (90.0 + phi):
        return None
    p = math.radians(phi)
    cp = math.radians(centerPhi)
    x = math.cos(math.radians(r)) - math.sin(cp) * math.sin(cp)
    u = math.cos(cp) * math.cos(p)
    y = math.sqrt(abs(u * u - x * x))
    return math.degrees(abs(math.atan2(y, x)))

def maxAlpha(r, centerPhi):
    """Computes alpha, the extent in longitude angle [-alpha, alpha] of the
    circle with radius r and center (0, centerPhi) on the unit sphere.
    Both r and centerPhi are assumed to be in units of degrees.
    centerPhi is clamped to lie in the range [-90,90] and r must
    lie in the range [0, 90].
    """
    assert r >= 0.0 and r <= 90.0
    if r == 0.0:
        return 0.0
    centerPhi = clampPhi(centerPhi)
    if abs(centerPhi) + r > 90.0 - POLE_EPSILON:
        return 180.0
    r = math.radians(r)
    c = math.radians(centerPhi)
    y = math.sin(r)
    x = math.sqrt(abs(math.cos(c - r) * math.cos(c + r)))
    return math.degrees(abs(math.atan(y / x)))

def cartesianAngularSep(v1, v2):
    """Returns the angular separation in degrees between points v1 and v2,
    which must both be specified as cartesian 3-vectors.
    """
    cs = dot(v1, v2)
    n = cross(v1, v2)
    ss = math.sqrt(dot(n, n))
    if cs == 0.0 and ss == 0.0:
        return 0.0
    return math.degrees(math.atan2(ss, cs))

def minEdgeSep(p, n, v1, v2):
    """Returns the minimum angular separation in degrees between p
    and points on the great circle edge with plane normal n and
    vertices v1, v2. All inputs must be unit cartesian 3-vectors.
    """
    p1 = cross(n, v1)
    p2 = cross(n, v2)
    if dot(p1, p) >= 0.0 and dot(p2, p) <= 0.0:
        return abs(90.0 - cartesianAngularSep(p, n))
    else:
        return min(cartesianAngularSep(p, v1), cartesianAngularSep(p, v2))

def minPhiEdgeSep(p, phi, minTheta, maxTheta):
    """Returns the minimum angular separation in degrees between p
    and points on the small circle edge with constant latitude angle
    phi and vertices (minTheta, phi), (maxTheta, phi). p must be in
    spherical coordinates.
    """
    if minTheta > maxTheta:
        if p[0] >= minTheta or p[0] <= maxTheta:
            return abs(p[1] - phi)
    else:
        if p[0] >= minTheta and p[0] <= maxTheta:
            return abs(p[1] - phi)
    return min(sphericalAngularSep(p, (minTheta, phi)),
               sphericalAngularSep(p, (maxTheta, phi)))

def minThetaEdgeSep(p, theta, minPhi, maxPhi):
    """Returns the minimum angular separation in degrees between p
    and points on the great circle edge with constant longitude angle
    theta and vertices (theta, minPhi), (theta, maxPhi). p must be a
    unit cartesian 3-vector.
    """
    v1 = unitVector(theta, minPhi)
    v2 = unitVector(theta, maxPhi)
    n = cross(v1, v2)
    d2 = dot(n, n)
    if d2 == 0.0:
        return min(cartesianAngularSep(p, v1), cartesianAngularSep(p, v2))
    return minEdgeSep(p, invScale(n, math.sqrt(d2)), v1, v2)

def centroid(vertices):
    """Computes the centroid of a set of vertices (which must be passed in
    as a list of cartesian unit vectors) on the unit sphere.
    """
    x, y, z = 0.0, 0.0, 0.0
    # Note: could use more accurate summation routines
    for v in vertices:
        x += v[0]
        y += v[1]
        z += v[2]
    return normalize((x, y, z))

def between(p, n, v1, v2):
    """Tests whether p lies on the shortest great circle arc from cartesian
    unit vectors v1 to v2, assuming that p is a unit vector on the plane
    defined by the origin, v1 and v2.
    """
    p1 = cross(n, v1)
    p2 = cross(n, v2)
    return dot(p1, p) >= 0.0 and dot(p2, p) <= 0.0

def segments(phiMin, phiMax, width):
    """Computes the number of segments to divide the given latitude angle
    range [phiMin, phiMax] (degrees) into. Two points within the range
    separated by at least one segment are guaranteed to have angular
    separation of at least width degrees.
    """
    p = max(abs(phiMin), abs(phiMax))
    if p > 90.0 - 1.0 * DEG_PER_ARCSEC:
        return 1
    if width >= 180.0:
        return 1
    elif width < 1.0 * DEG_PER_ARCSEC:
        width = 1.0 * DEG_PER_ARCSEC
    p = math.radians(p)
    cw = math.cos(math.radians(width))
    sp = math.sin(p)
    cp = math.cos(p)
    x = cw - sp * sp
    u = cp * cp
    y = math.sqrt(abs(u * u - x * x))
    return int(math.floor((2.0 * math.pi) / abs(math.atan2(y, x))))


# -- Regions on the unit sphere ----

class SphericalRegion(object):
    """Base class for regions on the unit sphere.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def contains(self, pointOrRegion):
        """Returns True if this spherical region contains the given point
        or spherical region.
        """

    @abc.abstractmethod
    def intersects(self, pointOrRegion):
        """Returns True if this spherical region intersects the given point
        or spherical region.
        """

    @abc.abstractmethod
    def getCenter(self):
        """Returns an 2-tuple of floats corresponding to the longitude/latitude
        angles (in degrees) of the center of the region.
        """
        return

    @abc.abstractmethod
    def getBoundingBox(self):
        """Returns a SphericalBox that bounds the region.
        """
        return


class SphericalBox(SphericalRegion):
    """A spherical coordinate space bounding box.

    This is similar to a bounding box in cartesian space in that
    it is specified by a pair of points; however, a spherical box may
    correspond to the entire unit-sphere, a spherical cap, a lune or
    the traditional rectangle. Additionally, spherical boxes can span
    the 0/360 degree longitude angle discontinuity.

    Note that points falling exactly on spherical box edges are
    considered to be inside (contained by) the box.
    """
    def __init__(self, *args):
        """
        Creates a new spherical box. If no arguments are supplied, then
        an empty box is created. If the arguments consist of a single
        SphericalRegion, then a copy of its bounding box is created.
        Otherwise, the arguments must consist of a pair of 2 (spherical)
        or 3 (cartesian 3-vector) element coordinate tuples/lists that
        specify the minimum/maximum longitude/latitude angles for the box.
        Latitude angles must be within [-90, 90] degrees, and the minimum
        latitude angle must be less than or equal to the maximum. If both
        minimum and maximum longitude angles lie in the range [0.0, 360.0],
        then the maximum can be less than the minimum. For example, a box
        with min/max longitude angles of 350/10 deg spans the longitude angle
        ranges [350, 360) and [0, 10]. Otherwise, the minimum must be less
        than or equal to the maximum, though values can be arbitrary. If
        the two are are separated by 360 degrees or more, then the box
        spans longitude angles [0, 360). Otherwise, both values are range
        reduced. For example, a spherical box with min/max longitude angles
        specified as 350/370 deg spans longitude angle ranges [350, 360) and
        [0, 10].
        """
        if len(args) == 0:
            self.setEmpty()
            return
        elif len(args) == 1:
            if isinstance(args[0], SphericalRegion):
                bbox = args[0].getBoundingBox()
                self.min = tuple(bbox.getMin())
                self.max = tuple(bbox.getMax())
                return
            args = args[0]
        if len(args) == 2:
            self.min = sphericalCoords(args[0])
            self.max = sphericalCoords(args[1])
        else:
            raise TypeError('Expecting a spherical region, 2 points, '
                            'or a tuple/list containing 2 points')
        if self.min[1] > self.max[1]:
            raise RuntimeError(
                'Latitude angle minimum is greater than maximum')
        if (self.max[0] < self.min[0] and
            (self.max[0] < 0.0 or self.min[0] > 360.0)):
            raise RuntimeError(
                'Longitude angle minimum is greater than maximum')
        # Range-reduce longitude angles
        if self.max[0] - self.min[0] >= 360.0:
            self.min = (0.0, self.min[1])
            self.max = (360.0, self.max[1])
        else:
            self.min = (reduceTheta(self.min[0]), self.min[1])
            self.max = (reduceTheta(self.max[0]), self.max[1])

    def wraps(self):
        """Returns True if this spherical box wraps across the 0/360
        degree longitude angle discontinuity.
        """
        return self.min[0] > self.max[0]

    def getBoundingBox(self):
        """Returns a bounding box for this spherical region.
        """
        return self

    def getMin(self):
        """Returns the minimum longitude and latitude angles of this
        spherical box as a 2-tuple of floats (in units of degrees).
        """
        return self.min

    def getMax(self):
        """Returns the maximum longitude and latitude angles of this
        spherical box as a 2-tuple of floats (in units of degrees).
        """
        return self.max

    def getThetaExtent(self):
        """Returns the extent in longitude angle of this box.
        """
        if self.wraps():
            return 360.0 - self.min[0] + self.max[0]
        else:
            return self.max[0] - self.min[0]

    def getCenter(self):
        """Returns an 2-tuple of floats corresponding to the longitude/latitude
        angles (in degrees) of the center of this spherical box.
        """
        centerTheta = 0.5 * (self.min[0] + self.max[0])
        centerPhi = 0.5 * (self.min[1] + self.max[1])
        if self.wraps():
            if centerTheta >= 180.0:
                centerTheta -= 180.0
            else:
                centerTheta += 180.0
        return (centerTheta, centerPhi)

    def isEmpty(self):
        """Returns True if this spherical box contains no points.
        """
        return self.min[1] > self.max[1]

    def isFull(self):
        """Returns True if this spherical box contains every point
        on the unit sphere.
        """
        return self.min == (0.0, -90.0) and self.max == (360.0, 90.0)

    def containsPoint(self, p):
        """Returns True if this spherical box contains the given point,
        which must be specified in spherical coordinates.
        """
        if p[1] < self.min[1] or p[1] > self.max[1]:
            return False
        theta = reduceTheta(p[0])
        if self.wraps():
            return theta >= self.min[0] or theta <= self.max[0]
        else:
            return theta >= self.min[0] and theta <= self.max[0]

    def contains(self, pointOrRegion):
        """Returns True if this spherical box completely contains the given
        point or spherical region.
        """
        if self.isEmpty():
            return False
        if isinstance(pointOrRegion, SphericalRegion):
            b = pointOrRegion.getBoundingBox()
            if b.isEmpty():
                return False
            if b.min[1] < self.min[1] or b.max[1] > self.max[1]:
                return False
            if self.wraps():
                if b.wraps():
                    return b.min[0] >= self.min[0] and b.max[0] <= self.max[0]
                else:
                    return b.min[0] >= self.min[0] or b.max[0] <= self.max[0]
            else:
                if b.wraps():
                    return self.min[0] == 0.0 and self.max[0] == 360.0
                else:
                    return b.min[0] >= self.min[0] and b.max[0] <= self.max[0]
        else:
            return self.containsPoint(sphericalCoords(pointOrRegion))

    def intersects(self, pointOrRegion):
        """Returns True if this spherical box intersects the given point
        or spherical region
        """
        if self.isEmpty():
            return False
        if isinstance(pointOrRegion, SphericalBox):
            b = pointOrRegion
            if b.isEmpty():
                return False
            if b.min[1] > self.max[1] or b.max[1] < self.min[1]:
                return False
            if self.wraps():
                if b.wraps():
                    return True
                else:
                    return b.min[0] <= self.max[0] or b.max[0] >= self.min[0]
            else:
                if b.wraps():
                    return self.min[0] <= b.max[0] or self.max[0] >= b.min[0]
                else:
                    return self.min[0] <= b.max[0] and self.max[0] >= b.min[0]
        elif isinstance(pointOrRegion, SphericalRegion):
            return pointOrRegion.intersects(self)
        else:
            return self.containsPoint(sphericalCoords(pointOrRegion))

    def extend(self, pointOrRegion):
        """Extends this box to the smallest spherical box S containing
        the union of this box with the specified point or spherical region.
        """
        if self == pointOrRegion:
            return self
        if isinstance(pointOrRegion, SphericalRegion):
            b = pointOrRegion.getBoundingBox()
            if b.isEmpty():
                return self
            elif self.isEmpty():
                self.min = tuple(b.min)
                self.max = tuple(b.max)
            minPhi = min(self.min[1], b.min[1])
            maxPhi = max(self.max[1], b.max[1])
            minTheta = self.min[0]
            maxTheta = self.max[0]
            if self.wraps():
                if b.wraps():
                    minMinRa = min(self.min[0], b.min[0])
                    maxMaxRa = max(self.max[0], b.max[0])
                    if maxMaxRa >= minMinRa:
                        minTheta = 0.0
                        maxTheta = 360.0
                    else:
                        minTheta = minMinRa
                        maxTheta = maxMaxRa
                else:
                    if b.min[0] <= self.max[0] and b.max[0] >= self.min[0]:
                        minTheta = 0.0
                        maxTheta = 360.0
                    elif b.min[0] - self.max[0] > self.min[0] - b.max[0]:
                        minTheta = b.min[0]
                    else:
                        maxTheta = b.max[0]
            else:
                if b.wraps():
                    if self.min[0] <= b.max[0] and self.max[0] >= b.min[0]:
                        minTheta = 0.0
                        maxTheta = 360.0
                    elif self.min[0] - b.max[0] > b.min[0] - self.max[0]:
                        maxTheta = b.max[0]
                    else:
                        minTheta = b.min[0]
                else:
                    if b.min[0] > self.max[0]:
                        if (360.0 - b.min[0] + self.max[0] <
                            b.max[0] - self.min[0]):
                            minTheta = b.min[0]
                        else:
                            maxTheta = b.max[0]
                    elif self.min[0] > b.max[0]:
                        if (360.0 - self.min[0] + b.max[0] <
                            self.max[0] - b.min[0]):
                            maxTheta = b.max[0]
                        else:
                            minTheta = b.min[0]
                    else:
                        minTheta = min(self.min[0], b.min[0])
                        maxTheta = max(self.max[0], b.max[0])
            self.min = (minTheta, minPhi)
            self.max = (maxTheta, maxPhi)
        else:
            p = sphericalCoords(pointOrRegion)
            theta, phi = reduceTheta(p[0]), p[1]
            if self.containsPoint(p):
                return self
            elif self.isEmpty():
                self.min = (theta, phi)
                self.max = (theta, phi)
            else:
                minPhi = min(self.min[1], phi)
                maxPhi = max(self.max[1], phi)
                minTheta = self.min[0]
                maxTheta = self.max[0]
                if self.wraps():
                    if self.min[0] - theta > theta - self.max[0]:
                        maxTheta = theta
                    else:
                        minTheta = theta
                elif theta < self.min[0]:
                    if self.min[0] - theta <= 360.0 - self.max[0] + theta:
                        minTheta = theta
                    else:
                        maxTheta = theta
                elif theta - self.max[0] <= 360.0 - theta + self.min[0]:
                    maxTheta = theta
                else:
                    minTheta = theta
                self.min = (minTheta, minPhi)
                self.max = (maxTheta, maxPhi)
        return self

    def shrink(self, box):
        """Shrinks this box to the smallest spherical box containing
        the intersection of this box and the specified one.
        """
        b = box
        if not isinstance(b, SphericalBox):
            raise TypeError('Expecting a SphericalBox object')
        if self == b or self.isEmpty():
            return self
        elif b.isEmpty():
            return self.setEmpty()
        minPhi = max(self.min[1], b.min[1])
        maxPhi = min(self.max[1], b.max[1])
        minTheta = self.min[0]
        maxTheta = self.max[0]
        if self.wraps():
            if b.wraps():
                minTheta = max(minTheta, b.min[0])
                maxTheta = min(maxTheta, b.max[0])
            else:
                if b.max[0] >= minTheta:
                    if b.min[0] <= maxTheta:
                        if b.max[0] - b.min[0] <= 360.0 - minTheta + maxTheta:
                            minTheta = b.min[0]
                            maxTheta = b.max[0]
                    else:
                        minTheta = max(minTheta, b.min[0])
                        maxTheta = b.max[0]
                elif b.min[0] <= maxTheta:
                    minTheta = b.min[0]
                    maxTheta = min(maxTheta, b.max[0])
                else:
                    minPhi = 90.0
                    maxPhi = -90.0
        else:
            if b.wraps():
                if maxTheta >= b.min[0]:
                    if minTheta <= b.max[0]:
                        if maxTheta - minTheta > 360.0 - b.min[0] + b.max[0]:
                            minTheta = b.min[0]
                            maxTheta = b.max[0]
                    else:
                        minTheta = max(minTheta, b.min[0])
                elif minTheta <= b.max[0]:
                    maxTheta = b.max[0]
                else:
                    minPhi = 90.0
                    maxPhi = -90.0
            elif minTheta > b.max[0] or maxTheta < b.min[0]:
                minPhi = 90.0
                maxPhi = -90.0
            else:
                minTheta = max(minTheta, b.min[0])
                maxTheta = min(maxTheta, b.max[0])
        self.min = (minTheta, minPhi)
        self.max = (maxTheta, maxPhi)
        return self

    def setEmpty(self):
        """Empties this spherical box.
        """
        self.min = (0.0, 90.0)
        self.max = (0.0, -90.0)
        return self

    def setFull(self):
        """Expands this spherical box to fill the unit sphere.
        """
        self.min = (0.0, -90.0)
        self.max = (360.0, 90.0)
        return self

    def __repr__(self):
        """Returns a string representation of this spherical box.
        """
        if self.isEmpty():
            return ''.join([self.__class__.__name__, '(', ')'])
        return ''.join([self.__class__.__name__, '(',
                        repr(self.min), ', ', repr(self.max), ')'])

    def __eq__(self, other):
        if isinstance(other, SphericalBox):
            if self.isEmpty() and other.isEmpty():
                return True
            return self.min == other.min and self.max == other.max
        return False

    @staticmethod
    def edge(v1, v2, n):
        """Returns a spherical bounding box for the great circle edge
        connecting v1 to v2 with plane normal n. All arguments must be
        cartesian unit vectors.
        """
        theta1, phi1 = sphericalCoords(v1)
        theta2, phi2 = sphericalCoords(v2)
        # Compute latitude angle range of the edge
        minPhi = min(phi1, phi2)
        maxPhi = max(phi1, phi2)
        d = n[0] * n[0] + n[1] * n[1]
        if abs(d) > MIN_FLOAT:
            # compute the 2 (antipodal) latitude angle extrema of n
            if abs(n[2]) <= SIN_MIN:
                ex = (0.0, 0.0, -1.0)
            else:
                ex = (n[0] * n[2] / d, n[1] * n[2] / d, -d)
            # check whether either extremum is inside the edge
            if between(ex, n, v1, v2):
                minPhi = min(minPhi, sphericalCoords(ex)[1])
            ex = (-ex[0], -ex[1], -ex[2])
            if between(ex, n, v1, v2):
                maxPhi = max(maxPhi, sphericalCoords(ex)[1])
        # Compute longitude angle range of the edge
        if abs(n[2]) <= SIN_MIN:
            # great circle is very close to a pole
            d = min(abs(theta1 - theta2), abs(360.0 - theta1 + theta2))
            if d >= 90.0 and d <= 270.0:
                # d is closer to 180 than 0/360: edge crosses over a pole
                minTheta = 0.0
                maxTheta = 360.0
            else:
                # theta1 and theta2 are nearly identical
                minTheta = min(theta1, theta2)
                maxTheta = max(theta1, theta2)
                if maxTheta - minTheta > 180.0:
                    # min/max on opposite sides of 0/360
                    # longitude angle discontinuity
                    tmp = maxTheta
                    maxTheta = minTheta
                    minTheta = tmp
        elif n[2] > 0.0:
            minTheta = theta1
            maxTheta = theta2
        else:
            minTheta = theta2
            maxTheta = theta1
        # return results
        return SphericalBox((minTheta, minPhi), (maxTheta, maxPhi))


class SphericalCircle(SphericalRegion):
    """A circle on the unit sphere. Points falling exactly on the
    circle are considered to be inside (contained by) the circle.
    """
    def __init__(self, center, radius):
        """Creates a new spherical circle with the given center and radius.
        """
        self.center = sphericalCoords(center)
        self.radius = float(radius)
        self.boundingBox = None
        if self.radius < 0.0 or self.radius > 180.0:
            raise RuntimeError(
                'Circle radius is negative or greater than 180 deg')
        self.center = (reduceTheta(self.center[0]), self.center[1])

    def getBoundingBox(self):
        """Returns a bounding box for this spherical circle.
        """
        if self.boundingBox is None:
            if self.isEmpty():
                self.boundingBox = SphericalBox()
            elif self.isFull():
                self.boundingBox = SphericalBox()
                self.boundingBox.setFull()
            else:
                alpha = maxAlpha(self.radius, self.center[1])
                minPhi = clampPhi(self.center[1] - self.radius)
                maxPhi = clampPhi(self.center[1] + self.radius)
                if alpha > 180.0 - ANGLE_EPSILON:
                    minTheta = 0.0
                    maxTheta = 360.0
                else:
                    minTheta = self.center[0] - alpha
                    maxTheta = self.center[0] + alpha
                self.boundingBox = SphericalBox((minTheta, minPhi),
                                                (maxTheta, maxPhi))
        return self.boundingBox

    def getBoundingCircle(self):
        return self

    def getCenter(self):
        """Returns an (ra, dec) 2-tuple of floats corresponding to the
        center of this circle.
        """
        return self.center

    def getRadius(self):
        """Returns the radius (degrees) of this circle.
        """
        return self.radius

    def isEmpty(self):
        """Returns True if this circle contains no points.
        """
        return self.radius < 0.0

    def isFull(self):
        """Returns True if this spherical box contains every point
        on the unit sphere.
        """
        return self.radius >= 180.0

    def contains(self, pointOrRegion):
        """Returns True if the specified point or spherical region is
        completely contained in this circle.
        """
        if self.isEmpty():
            return False
        pr = pointOrRegion
        c = self.center
        r = self.radius
        if isinstance(pr, SphericalBox):
            if pr.isEmpty():
                return False
            minp = pr.getMin()
            maxp = pr.getMax()
            if (sphericalAngularSep(c, minp) > r or
                sphericalAngularSep(c, maxp) > r or
                sphericalAngularSep(c, (minp[0], maxp[1])) > r or
                sphericalAngularSep(c, (maxp[0], minp[1])) > r):
                return False
            a = alpha(r, c[1], minp[1])
            if a is not None:
                if (pr.containsPoint((c[0] + a, minp[1])) or
                    pr.containsPoint((c[0] - a, minp[1]))):
                    return False
            a = alpha(r, c[1], maxp[1])
            if a is not None:
                if (pr.containsPoint((c[0] + a, maxp[1])) or
                    pr.containsPoint((c[0] - a, maxp[1]))):
                    return False
            return True
        elif isinstance(pr, SphericalCircle):
            if pr.isEmpty():
                return False
            return sphericalAngularSep(c, pr.center) <= r - pr.radius
        elif isinstance(pr, SphericalConvexPolygon):
            p = unitVector(c)
            for v in pr.getVertices():
                if cartesianAngularSep(p, v) > r:
                    return False
            return True
        else:
            return sphericalAngularSep(c, sphericalCoords(pr)) <= r

    def intersects(self, pointOrRegion):
        """Returns True if the given point or spherical region intersects
        this circle.
        """
        if self.isEmpty():
            return False
        pr = pointOrRegion
        c = self.center
        r = self.radius
        if isinstance(pr, SphericalBox):
            if pr.isEmpty():
                return False
            elif pr.containsPoint(c):
                return True
            minp = pr.getMin()
            maxp = pr.getMax()
            if (minPhiEdgeSep(c, minp[1], minp[0], maxp[0]) <= r or
                minPhiEdgeSep(c, maxp[1], minp[0], maxp[0]) <= r):
                return True
            p = unitVector(c)
            return (minThetaEdgeSep(p, minp[0], minp[1], maxp[1]) <= r or
                    minThetaEdgeSep(p, maxp[0], minp[1], maxp[1]) <= r)
        elif isinstance(pr, SphericalCircle):
            if pr.isEmpty():
                return False
            return sphericalAngularSep(c, pr.center) <= r + pr.radius
        elif isinstance(pr, SphericalConvexPolygon):
            return pr.intersects(self)
        else:
            return sphericalAngularSep(c, sphericalCoords(pr)) <= r

    def __repr__(self):
        """Returns a string representation of this circle.
        """
        return ''.join([self.__class__.__name__ , '(', repr(self.center),
                        ', ', repr(self.radius), ')'])

    def __eq__(self, other):
        if isinstance(other, SphericalCircle):
            if self.isEmpty() and other.isEmpty():
                return True
            if self.radius == other.radius:
                if self.center[1] == other.center[1]:
                    if abs(self.center[1]) == 90.0:
                        return True
                    return self.center[0] == other.center[0]
        return False


class SphericalConvexPolygon(SphericalRegion):
    """A convex polygon on the unit sphere with great circle edges. Points
    falling exactly on polygon edges are considered to be inside (contained
    by) the polygon.
    """
    def __init__(self, *args):
        """Creates a new polygon. Arguments must be either:

        1. a SphericalConvexPolygon
        2. a list of vertices
        3. a list of vertices and a list of corresponding edges

        In the first case, a copy is constructed. In the second case,
        the argument must be a sequence of 3 element tuples/lists
        (unit cartesian 3-vectors) - a copy of the vertices is stored
        and polygon edges are computed. In the last case, copies of the
        input vertex and edge lists are stored.

        Vertices must be hemispherical and in counter-clockwise order when
        viewed from outside the unit sphere in a right handed coordinate
        system. They must also form a convex polygon.

        When edges are specified, the i-th edge must correspond to the plane
        equation of great circle connecting vertices (i - 1, i), that is,
        the edge should be a unit cartesian 3-vector parallel to v[i-1] ^ v[i]
        (where ^ denotes the vector cross product).

        Note that these conditions are NOT verified for performance reasons.
        Operations on SphericalConvexPolygon objects constructed with inputs
        not satisfying these conditions are undefined. Use the convex()
        function to check for convexity and ordering of the vertices. Or,
        use the convexHull() function to create a SphericalConvexPolygon
        from an arbitrary list of hemispherical input vertices.
        """
        self.boundingBox = None
        self.boundingCircle = None
        if len(args) == 0:
            raise RuntimeError('Expecting at least one argument')
        elif len(args) == 1:
            if isinstance(args[0], SphericalConvexPolygon):
                self.vertices = list(args.vertices)
                self.edges = list(args.edges)
            else:
                self.vertices = list(args[0])
                self._computeEdges()
        elif len(args) == 2:
            self.vertices = list(args[0])
            self.edges = list(args[1])
            if len(self.edges) != len(self.vertices):
                raise RuntimeError(
                    'number of edges does not match number of vertices')
        else:
            self.vertices = list(args)
            self._computeEdges()
        if len(self.vertices) < 3:
            raise RuntimeError(
                'spherical polygon must contain at least 3 vertices')

    def _computeEdges(self):
        """Computes edge plane normals from vertices.
        """
        v = self.vertices
        n = len(v)
        edges = []
        for i in xrange(n):
            edges.append(normalize(cross(v[i - 1], v[i])))
        self.edges = edges

    def getVertices(self):
        """Returns the list of polygon vertices.
        """
        return self.vertices

    def getEdges(self):
        """Returns the list of polygon edges. The i-th edge is the plane
        equation for the great circle edge formed by vertices i-1 and i.
        """
        return self.edges

    def getBoundingCircle(self):
        """Returns a bounding circle (not necessarily minimal) for this
        spherical convex polygon.
        """
        if self.boundingCircle is None:
            center = centroid(self.vertices)
            radius = 0.0
            for v in self.vertices:
                radius = max(radius, cartesianAngularSep(center, v))
            self.boundingCircle = SphericalCircle(center, radius)
        return self.boundingCircle

    def getCenter(self):
        """Returns the centroid of this spherical convex polygon.
        """
        return self.getBoundingCircle().getCenter()

    def getBoundingBox(self):
        """Returns a bounding box for this spherical convex polygon.
        """
        if self.boundingBox is None:
            self.boundingBox = SphericalBox()
            for i in xrange(0, len(self.vertices)):
                self.boundingBox.extend(SphericalBox.edge(
                    self.vertices[i - 1], self.vertices[i], self.edges[i]))
        return self.boundingBox

    def getZRange(self):
        """Returns the z coordinate range spanned by this spherical
        convex polygon.
        """
        bbox = self.getBoundingBox()
        return (math.sin(math.radians(bbox.getMin()[1])),
                math.sin(math.radians(bbox.getMax()[1])))

    def clip(self, plane):
        """Returns the polygon corresponding to the intersection of this
        polygon with the positive half space defined by the given plane.
        The plane must be specified with a cartesian unit vector (its
        normal) and always passes through the origin.

        Clipping is performed using the Sutherland-Hodgman algorithm,
        adapted for spherical polygons.
        """
        vertices, edges, classification = [], [], []
        vin, vout = False, False
        for i in xrange(len(self.vertices)):
            d = dot(plane, self.vertices[i])
            if d > SIN_MIN: vin = True
            elif d < -SIN_MIN: vout = True
            else: d = 0.0
            classification.append(d)
        if not vin and not vout:
            # polygon and clipping plane are coplanar
            return None
        if not vout:
            return self
        elif not vin:
            return None
        v0 = self.vertices[-1]
        d0 = classification[-1]
        for i in xrange(len(self.vertices)):
            v1 = self.vertices[i]
            d1 = classification[i]
            if d0 > 0.0:
                if d1 >= 0.0:
                    # positive to positive, positive to zero: no intersection,
                    # add current input vertex to output polygon
                    vertices.append(v1)
                    edges.append(self.edges[i])
                else:
                    # positive to negative: add intersection point to polygon
                    f = d0 / (d0 - d1)
                    v = normalize((v0[0] + (v1[0] - v0[0]) * f,
                                   v0[1] + (v1[1] - v0[1]) * f,
                                   v0[2] + (v1[2] - v0[2]) * f))
                    vertices.append(v)
                    edges.append(self.edges[i])
            elif d0 == 0.0:
                if d1 >= 0.0:
                    # zero to positive: no intersection, add current input
                    # vertex to output polygon.
                    vertices.append(v1)
                    edges.append(self.edges[i])
                # zero to zero: coplanar edge - since the polygon has vertices
                # on both sides of plane, this implies concavity or a
                # duplicate vertex. Under the convexity assumption, this
                # must be caused by a near duplicate vertex, so skip the
                # vertex.
                #
                # zero to negative: no intersection, skip the vertex
            else:
                if d1 > 0.0:
                    # negative to positive: add intersection point to output
                    # polygon followed by the current input vertex
                    f = d0 / (d0 - d1)
                    v = normalize((v0[0] + (v1[0] - v0[0]) * f,
                                   v0[1] + (v1[1] - v0[1]) * f,
                                   v0[2] + (v1[2] - v0[2]) * f))
                    vertices.append(v)
                    edges.append(tuple(plane))
                    vertices.append(v1)
                    edges.append(self.edges[i])
                elif d1 == 0.0:
                    # negative to zero: add current input vertex to output
                    # polygon
                    vertices.append(v1)
                    edges.append(tuple(plane))
                # negative to negative: no intersection, skip vertex
            v0 = v1
            d0 = d1
        return SphericalConvexPolygon(vertices, edges)

    def intersect(self, poly):
        """Returns the intersection of poly with this polygon, or
        None if the intersection does not exist.
        """
        if not isinstance(poly, SphericalConvexPolygon):
            raise TypeError('Expecting a SphericalConvexPolygon object')
        p = self
        for edge in poly.getEdges():
            p = p.clip(edge)
            if p is None:
                break
        return p

    def area(self):
        """Returns the area of this spherical convex polygon.
        """
        numVerts = len(self.vertices)
        angleSum = 0.0
        for i in xrange(numVerts):
            tmp = cross(self.edges[i - 1], self.edges[i])
            sina = math.sqrt(dot(tmp, tmp))
            cosa = -dot(self.edges[i - 1], self.edges[i])
            a = math.atan2(sina, cosa)
            angleSum += a
        return angleSum - (numVerts - 2) * math.pi

    def containsPoint(self, v):
        for e in self.edges:
            if dot(v, e) < 0.0:
                return False
        return True

    def contains(self, pointOrRegion):
        """Returns True if the specified point or spherical region is
        completely contained in this polygon.
        """
        pr = pointOrRegion
        if isinstance(pr, SphericalConvexPolygon):
            for v in pr.getVertices():
                if not self.containsPoint(v):
                    return False
            return True
        elif isinstance(pr, SphericalCircle):
            cv = unitVector(pr.getCenter())
            if not self.containsPoint(cv):
                return False
            else:
                minSep = INF
                for i in xrange(len(self.vertices)):
                    s = minEdgeSep(cv, self.edges[i],
                                   self.vertices[i - 1], self.vertices[i])
                    minSep = min(minSep, s)
                return minSep >= pr.getRadius()
        elif isinstance(pr, SphericalBox):
            # check that all box vertices are inside the polygon
            bMin, bMax = pr.getMin(), pr.getMax()
            bzMin = math.sin(math.radians(bMin[1]))
            bzMax = math.sin(math.radians(bMax[1]))
            verts = map(unitVector,
                        (bMin, bMax, (bMin[0], bMax[1]), (bMax[0], bMin[1])))
            for v in verts:
                if not self.containsPoint(v):
                    return False
            # check that intersections of box small circles with polygon
            # edges either don't exist or fall outside the box.
            for i in xrange(len(self.vertices)):
                v0 = self.vertices[i - 1]
                v1 = self.vertices[i]
                e = self.edges[i]
                d = e[0] * e[0] + e[1] * e[1]
                if abs(e[2]) >= COS_MAX or d < MIN_FLOAT:
                    # polygon edge is approximately described by z = +/-1.
                    # box vertices are inside the polygon, so they
                    # cannot intersect the edge.
                    continue
                D = d - bzMin * bzMin
                if D >= 0.0:
                    # polygon edge intersects z = bzMin
                    D = math.sqrt(D)
                    xr = -e[0] * e[2] * bzMin
                    yr = -e[1] * e[2] * bzMin
                    i1 = ((xr + e[1] * D) / d, (yr - e[0] * D) / d, bzMin)
                    i2 = ((xr - e[1] * D) / d, (yr + e[0] * D) / d, bzMin)
                    if (pr.containsPoint(sphericalCoords(i1)) or
                        pr.containsPoint(sphericalCoords(i2))):
                        return False
                D = d - bzMax * bzMax
                if D >= 0.0:
                    # polygon edge intersects z = bzMax
                    D = math.sqrt(D)
                    xr = -e[0] * e[2] * bzMax
                    yr = -e[1] * e[2] * bzMax
                    i1 = ((xr + e[1] * D) / d, (yr - e[0] * D) / d, bzMax)
                    i2 = ((xr - e[1] * D) / d, (yr + e[0] * D) / d, bzMax)
                    if (pr.containsPoint(sphericalCoords(i1)) or
                        pr.containsPoint(sphericalCoords(i2))):
                        return False
            return True
        else:
            return self.containsPoint(unitVector(pr))

    def intersects(self, pointOrRegion):
        """Returns True if the given point or spherical region intersects
        this polygon.
        """
        pr = pointOrRegion
        if isinstance(pr, SphericalConvexPolygon):
            return self.intersect(pr) is not None
        elif isinstance(pr, SphericalCircle):
            cv = unitVector(pr.getCenter())
            if self.containsPoint(cv):
                return True
            else:
                minSep = INF
                for i in xrange(len(self.vertices)):
                    s = minEdgeSep(cv, self.edges[i],
                                   self.vertices[i - 1], self.vertices[i])
                    minSep = min(minSep, s)
                return minSep <= pr.getRadius()
        elif isinstance(pr, SphericalBox):
            minTheta = math.radians(pr.getMin()[0])
            maxTheta = math.radians(pr.getMax()[0])
            bzMin = math.sin(math.radians(pr.getMin()[1]))
            bzMax = math.sin(math.radians(pr.getMax()[1]))
            p = self.clip((-math.sin(minTheta), math.cos(minTheta), 0.0))
            if pr.getThetaExtent() > 180.0:
                if p is not None:
                    zMin, zMax = p.getZRange()
                    if zMin <= bzMax and zMax >= bzMin:
                        return True
                p = self.clip((math.sin(maxTheta), -math.cos(maxTheta), 0.0))
            else:
                if p is not None:
                    p = p.clip((math.sin(maxTheta), -math.cos(maxTheta), 0.0))
            if p is None:
                return False
            zMin, zMax = p.getZRange()
            return zMin <= bzMax and zMax >= bzMin
        else:
            return self.containsPoint(unitVector(pr))

    def __repr__(self):
        """Returns a string representation of this polygon.
        """
        return ''.join([self.__class__.__name__ , '(',
                        repr(map(sphericalCoords, self.vertices)), ')'])

    def __eq__(self, other):
        if not isinstance(other, SphericalConvexPolygon):
            return False
        n = len(self.vertices)
        if n != len(other.vertices):
            return False
        # Test for equality up to cyclic permutation of vertices/edges
        try:
            offset = other.vertices.index(self.vertices[0])
        except ValueError:
            return False
        for i in xrange(0, n):
            j = offset + i
            if j >= n:
                j -= n
            if (self.vertices[i] != self.vertices[j] or 
                self.edges[i] != self.edges[j]):
                return False
        return True


# -- Finding the median element of an array in linear time ----
#
# This is a necessary primitive for Megiddo's linear time
# 2d linear programming algorithm.

def _partition(array, left, right, i):
    """Partitions an array around the pivot value at index i,
    returning the new index of the pivot value.
    """
    pivot = array[i]
    array[i] = array[right - 1]
    j = left
    for k in xrange(left, right - 1):
        if array[k] < pivot:
            tmp = array[j]
            array[j] = array[k]
            array[k] = tmp
            j += 1
    array[right - 1] = array[j]
    array[j] = pivot
    return j

def _medianOfN(array, i, n):
    """Finds the median of n consecutive elements in an array starting
    at index i (efficient for small n). The index of the median element
    is returned.
    """
    if n == 1:
        return i
    k = n >> 1
    e1 = i + k + 1
    e2 = i + n
    for j in xrange(i, e1):
        minIndex = j
        minValue = array[j]
        for s in xrange(j + 1, e2):
            if array[s] < minValue:
                minIndex = s
                minValue = array[s]
        tmp = array[j]
        array[j] = array[minIndex]
        array[minIndex] = tmp
    return i + k

def _medianOfMedians(array, left, right):
    """Returns the "median of medians" for an array. This primitive is used
    for pivot selection in the median finding algorithm.
    """
    while True:
        if right - left <= 5:
            return _medianOfN(array, left, right - left)
        i = left
        j = left
        while i + 4 < right:
            k = _medianOfN(array, i, 5)
            tmp = array[j]
            array[j] = array[k]
            array[k] = tmp
            j += 1
            i += 5
        right = j

def median(array):
    """Finds the median element of the given array in linear time.
    """
    left = 0
    right = len(array)
    if right == 0:
        return None
    k = right >> 1
    while True:
        i = _medianOfMedians(array, left, right)
        i = _partition(array, left, right, i)
        if k == i:
            return array[k]
        elif k < i:
            right = i
        else:
            left = i + 1


# -- Testing whether a set of points is hemispherical ----
#
# This test is used by the convexity test and convex hull algorithm. It is
# implemented using Megiddo's algorithm for linear programming in R2, see:
#
# Megiddo, N. 1982. Linear-time algorithms for linear programming in R3 and related problems.
# In Proceedings of the 23rd Annual Symposium on Foundations of Computer Science (November 03 - 05, 1982).
# SFCS. IEEE Computer Society, Washington, DC, 329-338. DOI= http://dx.doi.org/10.1109/SFCS.1982.74

def _prune(constraints, xmin, xmax, op):
    """Removes redundant constraints and reports intersection points
    of non-redundant pairs. The constraint list is modified in place.
    """
    intersections = []
    i = 0
    while i < len(constraints) - 1:
        a1, b1 = constraints[i]
        a2, b2 = constraints[i + 1]
        # if constraints are near parallel or intersect to the left or right
        # of the feasible x range, remove the higher/lower constraint
        da = a1 - a2
        if abs(da) < MIN_FLOAT / EPSILON:
            xi = INF
        else:
            xi = (b2 - b1) / da
            xierr = 2.0 * EPSILON * abs(xi)
        if math.isinf(xi):
            if op(b1, b2):
                constraints[i + 1] = constraints[-1]
            else:
                constraints[i] = constraints[-1]
            constraints.pop()
        else:
            if xi + xierr <= xmin:
                if op(a1, a2):
                    constraints[i + 1] = constraints[-1]
                else:
                    constraints[i] = constraints[-1]
                constraints.pop()
            elif xi - xierr >= xmax:
                if op(a1, a2):
                    constraints[i] = constraints[-1]
                else:
                    constraints[i + 1] = constraints[-1]
                constraints.pop()
            else:
                # save intersection for later
                intersections.append((xi, xierr))
                i += 2
    return intersections

def _vrange(x, xerr, a, b):
    p = a * (x - xerr)
    v = p + b
    verr = EPSILON * abs(p) + EPSILON * abs(v)
    vmin = v - verr
    vmax = v + verr
    p = a * (x + xerr)
    v = p + b
    verr = EPSILON * abs(p) + EPSILON * abs(v)
    vmin = min(vmin, v - verr)
    vmax = max(vmax, v + verr)
    return vmin, vmax

def _gh(constraints, x, xerr, op):
    a, b = constraints[0]
    amin, amax = a, a
    vmin, vmax = _vrange(x, xerr, a, b)
    for i in xrange(1, len(constraints)):
        a, b = constraints[i]
        vimin, vimax = _vrange(x, xerr, a, b)
        if vimax < vmin or vimin > vmax:
            if op(vimin, vmin):
                amin = a
                amax = a
                vmin = vimin
                vmax = vimax
        else:
            amin = min(amin, a)
            amax = max(amax, a)
    return vmin, vmax, amin, amax

def _feasible2D(points, z):
    I1 = []
    I2 = []
    xmin = NEG_INF
    xmax = INF
    # transform each constraint of the form x*v[0] + y*v[1] + z*v[2] > 0
    # into y op a*x + b or x op c, where op is < or >
    for v in points:
        if abs(v[1]) <= MIN_FLOAT:
            if abs(v[0]) <= MIN_FLOAT:
                if z * v[2] <= 0.0:
                    # inequalities trivially lack a solution
                    return False
                # current inequality is trivially true, skip it
            else:
                xlim = - z * v[2] / v[0]
                if v[0] > 0.0:
                    xmin = max(xmin, xlim)
                else:
                    xmax = min(xmax, xlim)
                if xmax <= xmin:
                    # inequalities trivially lack a solution
                    return False
        else:
            # finite since |z|, |v[i]| <= 1 and 1/MIN_FLOAT is finite
            coeffs = (v[0] / v[1], - z * v[2] / v[1])
            if v[1] > 0.0:
                I1.append(coeffs)
            else:
                I2.append(coeffs)
    # At this point (xmin, xmax) is non-empty - if either I1 or I2 is empty
    # then a solution trivially exists
    if len(I1) == 0 or len(I2) == 0:
        return True
    # Check for a feasible solution to the inequalities I1 of the form
    # form y > a*x + b, I2 of the form y < a*x + b, x > xmin and x < xmax
    numConstraints = 0
    while True:
        intersections = _prune(I1, xmin, xmax, operator.gt)
        intersections.extend(_prune(I2, xmin, xmax, operator.lt))
        if len(intersections) == 0:
            # I1 and I2 each contain exactly one constraint
            a1, b1 = I1[0]
            a2, b2 = I2[0]
            if a1 == a2:
                xi = INF
            else:
                xi = (b2 - b1) / (a1 - a2)
            if math.isinf(xi):
                return b1 < b2
            return (xi > xmin or a1 < a2) and (xi < xmax or a1 > a2)
        elif numConstraints == len(I1) + len(I2):
            # No constraints were pruned during search interval refinement,
            # and g was not conclusively less than h. Conservatively return
            # False to avoid an infinite loop.
            return False
        numConstraints = len(I1) + len(I2)
        x, xerr = median(intersections)
        # If g(x) < h(x), x is a feasible solution. Otherwise, refine the
        # search interval by examining the one-sided derivates of g/h.
        gmin, gmax, sg, Sg = _gh(I1, x, xerr, operator.gt)
        hmin, hmax, sh, Sh = _gh(I2, x, xerr, operator.lt)
        if gmax <= hmin:
            return True
        elif sg > Sh:
            xmax = x + xerr
        elif Sg < sh:
            xmin = x - xerr
        else:
            return False

def _feasible1D(points, y):
    xmin = NEG_INF
    xmax = INF
    for v in points:
        if abs(v[0]) <= MIN_FLOAT:
            if y * v[1] <= 0.0:
                return False
            # inequality is trivially true, skip it
        else:
            xlim = - y * v[1] / v[0]
            if v[0] > 0.0:
                xmin = max(xmin, xlim)
            else:
                xmax = min(xmax, xlim)
            if xmax <= xmin:
                return False
    return True

def hemispherical(points):
    """Tests whether a set of points is hemispherical, i.e. whether a plane
    exists such that all points are strictly on one side of the plane. The
    algorithm used is Megiddo's algorithm for linear programming in R2 and
    has run-time O(n), where n is the number of points. Points must be passed
    in as a list of cartesian unit vectors.
    """
    # Check whether the set of linear equations
    # x * v[0] + y * v[1] + z * v[2] > 0.0 (for v in points)
    # has a solution (x, y, z). If (x,y,z) is a solution (is feasible),
    # so is C*(x,y,z), C > 0. Therefore we can fix z to 1, -1 and
    # perform 2D feasibility tests.
    if _feasible2D(points, 1.0):
        return True
    if _feasible2D(points, -1.0):
        return True
    # At this point a feasible solution must have z = 0. Fix y to 1, -1 and
    # perform 1D feasibility tests.
    if _feasible1D(points, 1.0):
        return True
    if _feasible1D(points, -1.0):
        return True
    # At this point a feasible solution must have y = z = 0. If all v[0]
    # are non-zero and have the same sign, then there is a feasible solution.
    havePos = False
    haveNeg = False
    for v in points:
        if v[0] > 0.0:
            if haveNeg:
                return False
            havePos = True
        elif v[0] < 0.0:
            if havePos:
                return False
            haveNeg = True
        else:
            return False
    return True


# -- Convexity test and convex hull algorithm ----

def convex(vertices):
    """Tests whether an ordered list of vertices (which must be specified
    as cartesian unit vectors) form a spherical convex polygon and determines
    their winding order. Returns a 2-tuple as follows:

    (True, True):   The vertex list forms a spherical convex polygon and is in
                    counter-clockwise order when viewed from outside the unit
                    sphere in a right handed coordinate system.
    (True, False):  The vertex list forms a spherical convex polygon and is in
                    in clockwise order.
    (False, msg):   The vertex list does not form a spherical convex polygon -
                    msg is a string describing why the test failed.

    The algorithm completes in O(n) time, where n is the number of
    input vertices.
    """
    if len(vertices) < 3:
        return (False, '3 or more vertices must be specified')
    if not hemispherical(vertices):
        return (False, 'vertices are not hemispherical')
    center = centroid(vertices)
    windingAngle = 0.0
    clockwise = False
    counterClockwise = False
    p1 = cross(center, vertices[-1])
    n2 = dot(p1, p1)
    if abs(n2) < CROSS_N2MIN:
        return (False, 'centroid of vertices is too close to a vertex')
    for i in xrange(len(vertices)):
        beg = vertices[i - 2]
        mid = vertices[i - 1]
        end = vertices[i]
        plane = cross(mid, end)
        n2 = dot(plane, plane)
        if dot(mid, end) >= COS_MAX or n2 < CROSS_N2MIN:
            return (False, 'vertex list contains [near-]duplicates')
        plane = invScale(plane, math.sqrt(n2))
        d = dot(plane, beg)
        if d > SIN_MIN:
            if clockwise:
                return (False, 'vertices wind around centroid in both ' +
                        'clockwise and counter-clockwise order')
            counterClockwise = True
        elif d < -SIN_MIN:
            if counterClockwise:
                return (False, 'vertices wind around centroid in both ' +
                        'clockwise and counter-clockwise order')
            clockwise = True
        # center must be inside polygon formed by vertices if they form a
        # convex polygon - an equivalent check is to test that polygon
        # vertices always wind around center in the same direction.
        d = dot(plane, center)
        if d < SIN_MIN and counterClockwise or d > -SIN_MIN and clockwise:
            return (False, 'centroid of vertices is not conclusively ' +
                    'inside all edges')
        # sum up winding angle for edge (mid, end)
        p2 = cross(center, end)
        n2 = dot(p2, p2)
        if abs(n2) < CROSS_N2MIN:
            return (False, 'centroid of vertices is too close to a vertex')
        windingAngle += cartesianAngularSep(p1, p2)
        p1 = p2
    # For convex polygons, the closest multiple of 360 to
    # windingAngle is 1.
    m = math.floor(windingAngle / 360.0)
    if m == 0.0 and windingAngle > 180.0 or m == 1.0 and windingAngle < 540.0:
        return (True, counterClockwise)
    return (False, 'vertices do not completely wind around centroid, or ' +
            'wind around it multiple times')

def convexHull(points):
    """Computes the convex hull (a spherical convex polygon) of an unordered
    list of points on the unit sphere, which must be passed in as cartesian
    unit vectors. The algorithm takes O(n log n) time, where n is the number
    of points.
    """
    if len(points) < 3:
        return None
    if not hemispherical(points):
        return None
    center = centroid(points)
    maxSep = 0.0
    extremum = 0
    # Vertex furthest from the center is on the hull
    for i in xrange(len(points)):
        sep = cartesianAngularSep(points[i], center)
        if sep > maxSep:
            extremum = i
            maxSep = sep
    anchor = points[extremum]
    refPlane = cross(center, anchor)
    n2 = dot(refPlane, refPlane)
    if n2 < CROSS_N2MIN:
        # vertex and center are too close
        return None
    refPlane = invScale(refPlane, math.sqrt(n2))
    # Order points by winding angle from the first (extreme) vertex
    av = [(0.0, anchor)]
    for i in xrange(0, len(points)):
        if i == extremum:
            continue
        v = points[i]
        plane = cross(center, v)
        n2 = dot(plane, plane)
        if n2 >= CROSS_N2MIN:
            plane = invScale(plane, math.sqrt(n2))
            p = cross(refPlane, plane)
            sa = math.sqrt(dot(p, p))
            if dot(p, center) < 0.0:
                sa = -sa
            angle = math.atan2(sa, dot(refPlane, plane))
            if angle < 0.0:
                angle += 2.0 * math.pi
            av.append((angle, v))
    if len(av) < 3:
        return None
    av.sort(key=lambda t: t[0]) # stable, so av[0] still contains anchor
    # Loop over vertices using a Graham scan adapted for spherical geometry.
    # Chan's algorithm would be an improvement, but seems likely to be slower
    # for small vertex counts (the expected case).
    verts = [anchor]
    edges = [None]
    edge = None
    i = 1
    while i < len(av):
        v = av[i][1]
        p = cross(anchor, v)
        n2 = dot(p, p)
        if dot(anchor, v) < COS_MAX and n2 >= CROSS_N2MIN:
            if edge is None:
                # Compute first edge
                edge = invScale(p, math.sqrt(n2))
                verts.append(v)
                edges.append(edge)
                anchor = v
            else:
                d = dot(v, edge)
                if d > SIN_MIN:
                    # v is inside the edge defined by the last
                    # 2 vertices on the hull
                    edge = invScale(p, math.sqrt(n2))
                    verts.append(v)
                    edges.append(edge)
                    anchor = v
                elif d < -SIN_MIN:
                    # backtrack - the most recently added hull vertex
                    # is not actually on the hull.
                    verts.pop()
                    edges.pop()
                    anchor = verts[-1]
                    edge = edges[-1]
                    # reprocess v to decide whether to add it to the hull
                    # or whether further backtracking is necessary
                    continue
                # v is coplanar with edge, skip it
        i += 1
    # Handle backtracking necessary for last edge
    if len(verts) < 3:
        return None
    v = verts[0]
    while True:
        p = cross(anchor, v)
        n2 = dot(p, p)
        if dot(anchor, v) < COS_MAX and n2 >= CROSS_N2MIN:
            if dot(v, edge) > SIN_MIN:
                edges[0] = invScale(p, math.sqrt(n2))
                break
        verts.pop()
        edges.pop()
        anchor = verts[-1]
        edge = edges[-1]
        if len(verts) < 3:
            return None
    return SphericalConvexPolygon(verts, edges)


def make_rectangle(ra, dec, s1, s2):
    """Creates a rectangular polygon for the given search region spec. Note
    this is not SIA compliant (SIA uses ra/dec boxes).
    """
    transform = pywcs.WCS()
    transform.naxis1 = 1
    transform.naxis2 = 1
    transform.wcs.ctype[0] = 'RA---TAN'
    transform.wcs.ctype[1] = 'DEC--TAN'
    transform.wcs.crval = [ra, dec]
    transform.wcs.crpix = [1.0, 1.0]
    transform.wcs.pc = numpy.array([[1.0, 0.0], [0.0, 1.0]], dtype=numpy.float64)
    transform.wcs.cdelt = [-s1, s2]
    transform.wcs.set()
    corners = numpy.zeros(shape=(4,2), dtype=numpy.float64)
    corners[0,0] = 0.5
    corners[0,1] = 0.5
    corners[1,0] = 1.5
    corners[1,1] = 0.5
    corners[2,0] = 1.5
    corners[2,1] = 1.5
    corners[3,0] = 0.5
    corners[3,1] = 1.5
    verts = transform.all_pix2sky(corners, 1)
    return convexHull(map(unitVector, verts))
