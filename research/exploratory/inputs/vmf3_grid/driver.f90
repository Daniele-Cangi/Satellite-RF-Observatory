! Adapter only: original TU Wien routine is included unchanged.
module original_vmf3
  implicit none
  type :: VMF3_grid_file_type
    character(len=17), dimension(:), allocatable :: filename
    character(len=:), allocatable :: indir_VMF3_grid
    double precision, dimension(:,:,:), allocatable :: VMF3_data_all
    double precision, dimension(:), allocatable :: orography_ell
    double precision :: lat, lon
  end type
contains
  include 'vmf3_grid.f90'
  subroutine evaluate(root, mjd, lat, lon, height, elevation, output)
    character(len=*), intent(in) :: root
    double precision, intent(in) :: mjd, lat, lon, height, elevation
    double precision, intent(out) :: output(4)
    character(len=:), allocatable :: directory
    type(VMF3_grid_file_type) :: cache
    double precision :: pi
    integer :: status, resolution
    pi = 4 * atan(1.0d0)
    directory = trim(root)
    resolution = 1
    call vmf3_grid(directory, directory, cache, mjd, lat*pi/180, lon*pi/180, &
                   height, (90-elevation)*pi/180, resolution, output(1), output(2), output(3), output(4))
    ! The upstream routine leaves orography unit 1 open. Each benchmark uses
    ! a fresh local cache, so close the unit before the next independent call.
    close(1, iostat=status)
  end subroutine
end module

program benchmark
  use original_vmf3
  implicit none
  character(len=2048) :: root
  double precision :: mjd, lat, lon, height, elevation, output(4)
  integer :: status
  call get_command_argument(1, root)
  do
    read(*, *, iostat=status) mjd, lat, lon, height, elevation
    if (status < 0) exit
    if (status /= 0) stop 1
    call evaluate(trim(root), mjd, lat, lon, height, elevation, output)
    write(*, '(4(ES25.16E3,1X))') output
  end do
end program
