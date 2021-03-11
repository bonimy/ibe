namespace fits {
template <size_t N>
arstring<N>::arstring() : str_(capacity) {}

template <size_t N>
arstring<N>::arstring(const char* str) : arstring() {
    std::strncpy(str_.data(), str, capacity);
}
template <size_t N>
arstring<N>::arstring(const std::string& str) : arstring(str.c_str()) {}

template <size_t N>
template <size_t M>
arstring<N>::arstring(const arstring<M>& right)
        : arstring(static_cast<const char*>(right)) {}

template <size_t N>
arstring<N>::arstring(const arstring&) = default;
template <size_t N>
arstring<N>::arstring(arstring&&) noexcept = default;

template <size_t N>
inline arstring<N>& arstring<N>::operator=(const char* right) {
    std::strncpy(str_.data(), right, capacity);
    return *this;
}
template <size_t N>
inline arstring<N>& arstring<N>::operator=(const std::string& right) {
    return *this = right.c_str();
}
template <size_t N>
template <size_t M>
inline arstring<N>& arstring<N>::operator=(const arstring<M>& right) {
    return *this = static_cast<const char*>(right);
}

template <size_t N>
inline arstring<N>& arstring<N>::operator=(arstring&) = default;
template <size_t N>
inline arstring<N>& arstring<N>::operator=(arstring&&) noexcept = default;

template <size_t N>
inline bool arstring<N>::operator==(const char* right) const {
    return std::strncmp(str_.data(), right, capacity) == 0;
}
template <size_t N>
inline bool arstring<N>::operator!=(const char* right) const {
    return !(*this == right);
}

template <size_t N>
inline bool arstring<N>::operator==(const std::string& right) const {
    return *this == right.c_str();
}
template <size_t N>
inline bool arstring<N>::operator!=(const std::string& right) const {
    return !(*this == right);
}

template <size_t N>
template <size_t M>
inline bool arstring<N>::operator==(const arstring<M>& right) const {
    return *this == static_cast<const char*>(right);
}
template <size_t N>
template <size_t M>
inline bool arstring<N>::operator!=(const arstring<M>& right) const {
    return !(*this == right);
}

template <size_t N>
inline bool arstring<N>::empty() const {
    return str_[0] == '\0';
}
template <size_t N>
inline size_t arstring<N>::size() const {

    // Cannot use `std::strlen` since there's risk of exceeding memory storage.
    for (size_t i = 0; i < capacity; i++) {
        if (str_[i] == '\0') return i;
    }
    return capacity + 1;
}

template <size_t N>
inline char& arstring<N>::operator[](size_t index) {
    return str_[index];
}
template <size_t N>
inline const char& arstring<N>::operator[](size_t index) const {
    return str_[index];
}

template <size_t N>
inline arstring<N>::operator char*() {
    return str_.data();
}
template <size_t N>
inline arstring<N>::operator const char*() const {
    return str_.data();
}

template <size_t N>
inline arstring<N>::operator std::string() {
    return str_.data();
}
template <size_t N>
inline arstring<N>::operator const std::string() const {
    return str_.data();
}

template <size_t N>
inline typename arstring<N>::iterator arstring<N>::begin() {
    return str_.begin();
}
template <size_t N>
inline typename arstring<N>::iterator arstring<N>::end() {
    return str_.end();
}

template <size_t N>
inline typename arstring<N>::const_iterator arstring<N>::begin() const {
    return str_.begin();
}
template <size_t N>
inline typename arstring<N>::const_iterator arstring<N>::end() const {
    return str_.end();
}

template <size_t N>
inline typename arstring<N>::const_iterator arstring<N>::cbegin() const {
    return str_.cbegin();
}
template <size_t N>
inline typename arstring<N>::const_iterator arstring<N>::cend() const {
    return str_.cend();
}

template <size_t N>
inline bool operator==(const char* left, const arstring<N>& right) {
    return right == left;
}
template <size_t N>
inline bool operator!=(const char* left, const arstring<N>& right) {
    return right != left;
}

template <size_t N>
inline bool operator==(const std::string& left, const arstring<N>& right) {
    return right == left;
}
template <size_t N>
inline bool operator!=(const std::string& left, const arstring<N>& right) {
    return right != left;
}

template <size_t N, class Elem, class Traits>
inline std::basic_ostream<Elem, Traits>& operator<<(std::basic_ostream<Elem, Traits>& s,
                                                    const arstring<N>& str) {
    return std::operator<<(s, static_cast<const char*>(str));
}

template <size_t N, class Elem, class Traits>
inline std::basic_istream<Elem, Traits>& operator>>(std::basic_istream<Elem, Traits>& s,
                                                    const arstring<N>& str) {
    return std::operator>>(s, static_cast<const char*>(str));
}
}  // namespace fits
