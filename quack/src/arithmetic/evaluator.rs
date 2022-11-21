use crate::arithmetic::ModularInteger;

pub struct MonicPolynomialEvaluator {
}

impl MonicPolynomialEvaluator {
    /// Evaluate the univariate polynomial with the given coefficients using
    /// modular arithmetic, assuming all coefficients are modulo the same
    /// 32-bit prime. In the coefficient vector, the last element is the
    /// constant term in the polynomial. The number of coefficients is the
    /// degree of the polynomial. The leading coefficient is 1, and is not
    /// included in the vector.
    pub fn eval(coeffs: &Vec<ModularInteger>, x: u32) -> ModularInteger {
        let size = coeffs.len();
        let x_mod = ModularInteger::new(x);
        let mut result = x_mod;
        // result = x(...(x(x(x+a0)+a1)+...))
        // e.g., result = x(x+a0)+a1
        for i in 0..(size - 1) {
            result += coeffs[i];
            result *= x_mod;
        }
        result + coeffs[size - 1]
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn test_eval_no_modulus() {
        // f(x) = x^2 + 2*x - 3
        // f(0) = -3
        // f(1) = 0
        // f(2) = 5
        // f(3) = 12
        let coeffs = vec![ModularInteger::new(2), -ModularInteger::new(3)];
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 0), -ModularInteger::new(3));
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 1), 0);
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 2), 5);
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 3), 12);
    }

    #[test]
    fn test_eval_with_modulus() {
        let coeffs = vec![
            ModularInteger::new(2539233112),
            ModularInteger::new(2884903207),
            ModularInteger::new(3439674878),
        ];

        // Test zeros.
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 95976998), 0);
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 456975625), 0);
        assert_eq!(MonicPolynomialEvaluator::eval(&coeffs, 1202781556), 0);

        // Test other points.
        assert_ne!(MonicPolynomialEvaluator::eval(&coeffs, 2315971647), 0);
        assert_ne!(MonicPolynomialEvaluator::eval(&coeffs, 3768947911), 0);
        assert_ne!(MonicPolynomialEvaluator::eval(&coeffs, 1649073968), 0);
    }
}
