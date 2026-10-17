---
title: Math and executable notes
---
@toc
# Math and executable notes

A standalone page with $e^{i\pi}+1=0$, an inline fraction $\frac{a+b}{c+d}$, and a Gaussian integral:

$$\int_{-\infty}^{\infty} e^{-x^2}\,dx=\sqrt{\pi}$$

## Matrices and aligned equations

$$\begin{pmatrix}1 & 2 \\ 3 & 4\end{pmatrix}\begin{pmatrix}x\\y\end{pmatrix}$$

$$\begin{aligned}f(x)&=x^2+2x+1\\&=(x+1)^2\end{aligned}$$

## Executable examples

@src-begin(python, expanded)
# Liquid braces remain source code.
print({"result": sum(n*n for n in range(8))})
@src-end

## Exercises

### Exercise 1

Find the derivative of $\sin(x^2)$.

### Solution

The derivative is $2x\cos(x^2)$.

### Exercise 2

Evaluate $\sum_{n=1}^{\infty}\frac{1}{n^2}$.
