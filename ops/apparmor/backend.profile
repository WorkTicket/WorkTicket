#include <tunables/global>

profile workticket-backend flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/python>

  network tcp,
  network udp,
  network inet stream,
  network inet dgram,

  /tmp/* rw,
  /var/run/* rw,
  /proc/@{pid}/fd/ r,

  # Application write paths — configure per deployment:
  #   UPLOAD_DIR: Default /var/lib/workticket/uploads/ (file uploads, media processing)
  #   WORK_DIR:   Default /var/lib/workticket/work/     (scratch space, temp artifacts)
  /var/lib/workticket/uploads/** rw,
  /var/lib/workticket/uploads/ rw,
  /var/lib/workticket/work/** rw,
  /var/lib/workticket/work/ rw,

  # Logging — allow write for structured and audit logs
  /var/log/** rw,
  /var/log/ rw,

  deny /** w,
  deny /** m,
}
