"""Independent circular solution, conserved central force and light time."""
import numpy as np
import pytest

from research.kinematic import orbital_dynamics as model
from research.kinematic.receiver_time import predict, rotate_z


def circular(seconds):
    radius = 27e6  # invented synthetic satellite, not a real-target radius prior
    frequency = np.sqrt(model.MU/radius**3)-model.OMEGA
    angle = np.asarray(seconds)*frequency
    p = radius*np.stack([np.cos(angle),np.sin(angle),np.zeros_like(angle)],axis=-1)
    v = radius*frequency*np.stack([-np.sin(angle),np.cos(angle),np.zeros_like(angle)],axis=-1)
    return np.concatenate([p,v],axis=-1)


def test_circular_orbit_in_rotating_frame_both_time_directions():
    trajectory = model.Trajectory(circular(0),[-3600,3600],j2=0.)
    times = np.array([-3600.,-900.,0.,900.,3600.])
    expected,actual = circular(times),trajectory(times)
    assert np.max(np.linalg.norm(expected[:,:3]-actual[:,:3],axis=1))<1e-4
    assert np.max(np.linalg.norm(expected[:,3:]-actual[:,3:],axis=1))<1e-7
    assert trajectory(np.empty((0,2))).shape==(0,2,6)
    with pytest.raises(ValueError,match='bounds'):
        trajectory(3600.01)


def test_central_inertial_energy_and_angular_momentum_are_conserved():
    seed = np.array([26e6,2e6,4e6,-250.,1800.,500.])
    t = np.linspace(-1800,1800,25)
    states = model.Trajectory(seed,[-1800,1800],j2=0.)(t)
    p = rotate_z(states[:,:3],model.OMEGA*t)
    v = rotate_z(states[:,3:]+np.cross([0,0,model.OMEGA],states[:,:3]),model.OMEGA*t)
    energy = np.sum(v*v,axis=1)/2-model.MU/np.linalg.norm(p,axis=1)
    angular = np.cross(p,v)
    assert np.ptp(energy)/abs(energy[0])<1e-11
    assert np.max(np.linalg.norm(angular-angular[0],axis=1))/np.linalg.norm(angular[0])<1e-11


def test_j2_acceleration_has_independent_equatorial_and_polar_limits():
    radius = 27e6
    factor = 1.5*model.J2*model.MU*model.R_EARTH**2/radius**4
    equator = np.r_[radius,0.,0.,0.,0.,0.]
    pole = np.r_[0.,0.,radius,0.,0.,0.]
    assert model.acceleration(equator)-model.acceleration(equator,j2=0.)==pytest.approx([-factor,0.,0.],abs=1e-15)
    assert model.acceleration(pole)-model.acceleration(pole,j2=0.)==pytest.approx([0.,0.,2*factor],abs=1e-15)
    with pytest.raises(ValueError,match='exterior'):
        model.Trajectory(np.zeros(6),[-1,1])


def test_dynamic_light_time_matches_quadratic_contract_for_the_same_trajectory():
    state = np.array([26e6,2e6,4e6,-250.,2300.,500.,-.52,-.04,-.08,75000.,12.])
    def quadratic(t):
        t = np.asarray(t)
        return np.concatenate([state[:3]+t[...,None]*state[3:6]+.5*t[...,None]**2*state[6:9],
                               state[3:6]+t[...,None]*state[6:9]],axis=-1)
    stations = np.array([[6378137.,0.,0.],[0.,6378137.,0.],[0.,0.,6378137.]])
    clocks = np.array([[1000.,.001],[-2000.,-.002],[700.,.0005]])
    tags = np.array([-60.,-30.,0.,30.])
    old = predict(state,tags,stations,clocks)['code_m']
    new = model.predict_codes(quadratic,0.,tags,stations,clocks,state[9:])
    assert new==pytest.approx(old,rel=0.,abs=1e-8)


def test_light_time_with_analytic_circular_motion_and_transmit_clock():
    stations = np.array([[6378137.,0,0]])
    tags = np.array([-60.,0.,60.])
    clocks = np.array([[1000.,.001]])
    satellite_clock = [70000.,.02]
    receive = tags-clocks[0,0]/model.C-tags*clocks[0,1]/model.C
    tau = np.full(len(tags),.08)
    for _ in range(30):
        rho = np.linalg.norm(rotate_z(circular(receive-tau)[:,:3],-model.OMEGA*tau)-stations[0],axis=1)
        tau = rho/model.C
    expected = rho+clocks[0,0]+tags*clocks[0,1]-satellite_clock[0]-satellite_clock[1]*(receive-tau)
    curve = model.Trajectory(circular(0),[-100,100],j2=0.)
    assert model.predict_codes(curve,0.,tags,stations,clocks,satellite_clock)[:,0]==pytest.approx(expected,rel=0,abs=2e-5)


@pytest.mark.parametrize('j2',[0.,model.J2])
def test_force_and_integrated_variational_derivatives_match_independent_perturbations(j2):
    seed = np.array([26e6,2e6,4e6,-250.,1800.,500.])
    steps = np.array([100.,100.,100.,.01,.01,.01])
    rhs = lambda y:np.r_[y[3:],model.acceleration(y,j2=j2)]
    numerical = np.column_stack([(rhs(seed+e)-rhs(seed-e))/(2*h)
                for e,h in zip(np.diag(steps),steps,strict=True)])
    np.testing.assert_allclose(model.force_jacobian(seed,j2=j2),numerical,rtol=1e-6,atol=1e-12)
    curve = model.Trajectory(seed,[-3600,3600],j2=j2,sensitivities=True)
    times = np.array([-3500.,0.,3500.])
    columns = [(model.Trajectory(seed+e,[-3600,3600],j2=j2)(times)-
                model.Trajectory(seed-e,[-3600,3600],j2=j2)(times))/(2*h)
               for e,h in zip(np.diag(steps),steps,strict=True)]
    np.testing.assert_allclose(curve.state_jacobian(times),np.stack(columns,axis=-1),rtol=1e-6,atol=1e-6)


def test_observation_derivatives_include_light_time_rotation_and_both_clocks():
    seed = np.array([26e6,2e6,4e6,-250.,1800.,500.])
    stations = np.array([[6378137.,0.,0.],[0.,6378137.,0.]])
    clocks = np.array([[1000.,.01],[-2000.,-.02]])
    tags = np.array([-60.,-30.,0.])
    curve = model.Trajectory(seed,[-100,1900],sensitivities=True)
    prediction = model.predict_observations(curve,1800.,tags,stations,clocks,[75000.,12.])
    steps = np.array([100.,100.,100.,.01,.01,.01])
    for k,(e,h) in enumerate(zip(np.diag(steps),steps,strict=True)):
        plus = model.predict_codes(model.Trajectory(seed+e,[-100,1900]),1800.,tags,stations,clocks,[75000.,12.])
        minus = model.predict_codes(model.Trajectory(seed-e,[-100,1900]),1800.,tags,stations,clocks,[75000.,12.])
        np.testing.assert_allclose(prediction['initial_state_derivative'][...,k],(plus-minus)/(2*h),rtol=1e-6,atol=1e-6)
    for j in range(2):
        for k,h in enumerate([10.,.1]):
            change = np.zeros_like(clocks); change[j,k]=h
            plus = model.predict_codes(curve,1800.,tags,stations,clocks+change,[75000.,12.])
            minus = model.predict_codes(curve,1800.,tags,stations,clocks-change,[75000.,12.])
            expected = prediction['receiver_clock_derivative'][:,j]*(tags if k else 1.)
            np.testing.assert_allclose((plus-minus)[:,j]/(2*h),expected,rtol=1e-6,atol=1e-7)
        for k in range(3):
            change = np.zeros_like(stations); change[j,k]=10.
            plus = model.predict_codes(curve,1800.,tags,stations+change,clocks,[75000.,12.])
            minus = model.predict_codes(curve,1800.,tags,stations-change,clocks,[75000.,12.])
            np.testing.assert_allclose((plus-minus)[:,j]/20.,prediction['station_derivative'][:,j,k],rtol=1e-6,atol=1e-7)
