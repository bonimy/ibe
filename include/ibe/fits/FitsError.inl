namespace fits {
FITSError::FITSError(int status) : FitsException(get_error_message(status), status) {}
}  // namespace fits
